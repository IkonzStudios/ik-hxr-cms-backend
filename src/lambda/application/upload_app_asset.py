import json
import os
import re
import mimetypes
import boto3
from typing import Dict, Any

from utils.helpers import (
    get_cors_headers,
    create_error_response,
    parse_request_body,
)
from utils.rbac import check_create_permission_with_org


# Asset types supported for SWA application uploads
ZIP_ASSET = "zip"
VIDEO_ASSET = "video"
VALID_ASSET_TYPES = [ZIP_ASSET, VIDEO_ASSET]


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to generate a presigned POST for uploading SWA application assets
    (build zip and videos) directly to S3.

    Expected request body:
    {
        "app_name": "SBI",
        "file_name": "intro.mp4",
        "asset_type": "video",            # "zip" | "video"
        "organization_id": "123e4567-e89b-12d3-a456-426614174000"
    }

    S3 key layout (file name is preserved, never renamed):
        zip   -> apps/{app_name}/zip/{file_name}
        video -> apps/{app_name}/media/videos/{file_name}

    Returns:
    - 200: Success with presigned POST (upload_url + fields + s3_key)
    - 400: Bad request (missing/invalid params)
    - 403: Forbidden (user lacks permission)
    - 500: Internal server error
    """

    try:
        # Get S3 bucket name from environment variable
        bucket_name = os.environ.get("CONTENT_BUCKET_NAME")
        if not bucket_name:
            raise ValueError("CONTENT_BUCKET_NAME environment variable not set")

        # Debug: Print the event structure
        print(f"Event: {json.dumps(event)}")

        # Parse request body
        body, parse_error = parse_request_body(event)
        if parse_error:
            return parse_error

        app_name = (body.get("app_name") or "").strip()
        file_name = (body.get("file_name") or "").strip()
        asset_type = (body.get("asset_type") or "").strip().lower()
        organization_id = body.get("organization_id", "")

        # Validate required params
        if not app_name:
            return create_error_response(400, "app_name is required")
        if not file_name:
            return create_error_response(400, "file_name is required")
        if not organization_id:
            return create_error_response(400, "organization_id is required")
        if asset_type not in VALID_ASSET_TYPES:
            return create_error_response(
                400, f"asset_type must be one of: {', '.join(VALID_ASSET_TYPES)}"
            )

        # RBAC: only users allowed to create applications in this org can upload assets
        rbac_error, user_info = check_create_permission_with_org(
            event, "application", organization_id
        )
        if rbac_error:
            return rbac_error

        print(
            f"User {user_info['user_id']} ({user_info['role']}) uploading "
            f"{asset_type} asset '{file_name}' for app '{app_name}' in org {organization_id}"
        )

        # Validate names to keep the S3 key safe (no path traversal / separators)
        if not is_safe_path_segment(app_name):
            return create_error_response(
                400,
                "Invalid app_name. Only alphanumeric characters, spaces, dots, hyphens, and underscores are allowed",
            )
        if not is_safe_path_segment(file_name):
            return create_error_response(
                400,
                "Invalid file name. Only alphanumeric characters, spaces, dots, hyphens, and underscores are allowed",
            )

        # Enforce extension matches the declared asset type
        extension = get_file_extension(file_name)
        if asset_type == ZIP_ASSET and extension != "zip":
            return create_error_response(400, "zip asset_type requires a .zip file")
        if asset_type == VIDEO_ASSET and not is_video_extension(extension):
            return create_error_response(400, "video asset_type requires a video file")

        # Build the S3 key. File name is preserved exactly (no rename).
        if asset_type == ZIP_ASSET:
            s3_key = f"apps/{app_name}/zip/{file_name}"
        else:
            s3_key = f"apps/{app_name}/media/videos/{file_name}"

        # Generate presigned POST for the direct browser upload
        presigned_post = generate_presigned_post(bucket_name, s3_key, file_name)

        return {
            "statusCode": 200,
            "headers": get_cors_headers(),
            "body": json.dumps(
                {
                    "message": "Presigned POST generated successfully",
                    "data": {
                        "upload_url": presigned_post["url"],
                        "fields": presigned_post["fields"],
                        "s3_key": s3_key,
                        "file_url": s3_key,
                        "bucket_name": bucket_name,
                        "original_file_name": file_name,
                        "app_name": app_name,
                        "asset_type": asset_type,
                        "organization_id": organization_id,
                        "expires_in": 3600,  # 1 hour
                    },
                }
            ),
        }

    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        print(f"Error generating presigned POST for app asset: {str(e)}")
        import traceback

        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, "Internal server error")


def is_safe_path_segment(value: str) -> bool:
    """
    Validate a value used as an S3 key segment to prevent path traversal.

    Allows alphanumeric characters, spaces, dots, hyphens, and underscores.
    Rejects slashes and ".." sequences.
    """
    if ".." in value:
        return False
    return bool(re.match(r"^[a-zA-Z0-9\s\.\-_]+$", value))


def get_file_extension(filename: str) -> str:
    """Extract the lowercase file extension (without dot), or '' if none."""
    if "." in filename:
        return filename.rsplit(".", 1)[1].lower()
    return ""


def is_video_extension(extension: str) -> bool:
    """Return True if the extension is a recognised video format."""
    return extension in {"mp4", "mov", "avi", "mkv", "webm", "m4v", "mpeg", "mpg"}


def generate_presigned_post(
    bucket_name: str, s3_key: str, file_name: str
) -> Dict[str, Any]:
    """
    Generate a presigned POST for uploading a file to S3.

    Args:
        bucket_name: The S3 bucket name
        s3_key: The S3 key (path) where the file will be stored
        file_name: The original file name (for content-type detection)

    Returns:
        Dictionary containing presigned POST URL and fields
    """
    region = os.environ.get("AWS_REGION")
    s3_client = boto3.client(
        "s3",
        endpoint_url=f"https://s3.{region}.amazonaws.com",
    )

    content_type = get_content_type(file_name)

    presigned_post = s3_client.generate_presigned_post(
        Bucket=bucket_name,
        Key=s3_key,
        Fields={"Content-Type": content_type},
        Conditions=[{"Content-Type": content_type}],
        ExpiresIn=3600,  # 1 hour
    )

    return presigned_post


def get_content_type(filename: str) -> str:
    """Determine the content type from a file extension, defaulting to binary."""
    content_type, _ = mimetypes.guess_type(filename)
    if content_type is None:
        # zip often resolves, but guard the fallback regardless
        if get_file_extension(filename) == "zip":
            return "application/zip"
        content_type = "application/octet-stream"
    return content_type
