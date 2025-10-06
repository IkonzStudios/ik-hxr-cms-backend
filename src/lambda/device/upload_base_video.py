import json
import os
import boto3
import uuid
from typing import Dict, Any, Tuple, Optional
from datetime import datetime
from botocore.exceptions import ClientError
from botocore.config import Config
from utils.rbac import check_upload_permission_with_org


def get_cors_headers() -> Dict[str, str]:
    """
    Get standard CORS headers for all responses.

    Returns:
        Dictionary with CORS headers
    """
    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token",
        "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
        "Access-Control-Max-Age": "86400",
    }


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to generate presigned URLs for base video uploads to devices.

    Expected event structure:
    {
        "pathParameters": {
            "device_id": "device-123"
        },
        "body": {
            "file_name": "base_video.mp4"
        },
        "requestContext": {
            "authorizer": {
                "context": {
                    "organization_id": "123e4567-e89b-12d3-a456-426614174000",
                    "user_id": "user-123",
                    "email": "user@example.com",
                    "role": "admin"
                }
            }
        }
    }
    """

    try:
        # Get environment variables
        bucket_name = os.environ.get("CONTENT_BUCKET_NAME")
        if not bucket_name:
            raise ValueError("CONTENT_BUCKET_NAME environment variable not set")

        # Extract device ID from path parameters
        device_id = event.get("pathParameters", {}).get("id")
        if not device_id:
            return {
                "statusCode": 400,
                "headers": get_cors_headers(),
                "body": json.dumps({"error": "Device ID is required in path parameters"}),
            }

        # Parse request body
        body = json.loads(event.get("body", "{}"))
        file_name = body.get("file_name")

        if not file_name:
            return {
                "statusCode": 400,
                "headers": get_cors_headers(),
                "body": json.dumps({"error": "file_name is required"}),
            }

        # Get device information to extract organization_id
        device_info, device_error = get_device_by_id(device_id)
        if device_error:
            return device_error

        organization_id = device_info.get("organization_id")
        if not organization_id:
            return {
                "statusCode": 400,
                "headers": get_cors_headers(),
                "body": json.dumps({"error": "Device organization not found"}),
            }

        # RBAC: Check if user has permission to upload base video for devices in this organization
        rbac_error, user_info = check_upload_permission_with_org(event, "device", organization_id)
        if rbac_error:
            return rbac_error

        # Log user action for audit
        print(f"User {user_info['user_id']} ({user_info['role']}) uploading base video for device {device_id} in org {organization_id}")

        # Validate file name
        if not is_valid_filename(file_name):
            return {
                "statusCode": 400,
                "headers": get_cors_headers(),
                "body": json.dumps(
                    {
                        "error": "Invalid file name. Only alphanumeric characters, spaces, dots, hyphens, and underscores are allowed"
                    }
                ),
            }

        # Generate UUID for file naming
        file_uuid = str(uuid.uuid4())
        file_extension = get_file_extension(file_name)
        uuid_filename = f"{file_uuid}.{file_extension}" if file_extension else file_uuid

        # Create S3 key with base-contents structure and UUID filename
        s3_key = f"base-contents/{organization_id}/{uuid_filename}"

        # Generate presigned POST instead of PUT
        presigned_post = generate_presigned_post(bucket_name, s3_key, file_name)

        # Create file_url in the required format
        file_id = f"base-contents/{organization_id}/{uuid_filename}"

        return {
            "statusCode": 200,
            "headers": get_cors_headers(),
            "body": json.dumps(
                {
                    "message": "Presigned POST generated successfully for base video upload",
                    "data": {
                        "upload_url": presigned_post["url"],
                        "fields": presigned_post["fields"],
                        "s3_key": s3_key,
                        "file_url": file_id,
                        "bucket_name": bucket_name,
                        "original_file_name": file_name,
                        "device_id": device_id,
                        "organization_id": organization_id,
                        "expires_in": 3600,  # 1 hour
                    },
                }
            ),
        }

    except json.JSONDecodeError:
        return {
            "statusCode": 400,
            "headers": get_cors_headers(),
            "body": json.dumps({"error": "Invalid JSON in request body"}),
        }
    except Exception as e:
        print(f"Error generating presigned POST: {str(e)}")
        return {
            "statusCode": 500,
            "headers": get_cors_headers(),
            "body": json.dumps({"error": "Internal server error"}),
        }


def get_device_by_id(device_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Get device by ID from DynamoDB.

    Args:
        device_id: The device ID to fetch

    Returns:
        Tuple of (device_data, error_response)
        If successful: (device_dict, None)
        If error: (None, error_response_dict)
    """
    try:
        table_name = os.environ.get("DEVICES_TABLE_NAME")
        if not table_name:
            return None, {
                "statusCode": 500,
                "headers": get_cors_headers(),
                "body": json.dumps({"error": "DEVICES_TABLE_NAME environment variable not set"}),
            }

        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)

        response = table.get_item(Key={"id": device_id})

        if "Item" not in response:
            return None, {
                "statusCode": 404,
                "headers": get_cors_headers(),
                "body": json.dumps({"error": "Device not found"}),
            }

        return response["Item"], None

    except Exception as e:
        print(f"Error getting device: {str(e)}")
        return None, {
            "statusCode": 500,
            "headers": get_cors_headers(),
            "body": json.dumps({"error": "Internal server error"}),
        }


def is_valid_filename(filename: str) -> bool:
    """
    Validate filename to ensure it only contains safe characters.

    Args:
        filename: The filename to validate

    Returns:
        True if filename is valid, False otherwise
    """
    import re

    # Allow alphanumeric characters, spaces, dots, hyphens, and underscores
    # Also allow common file extensions
    pattern = r"^[a-zA-Z0-9\s\.\-_]+$"

    return bool(re.match(pattern, filename))


def get_file_extension(filename: str) -> str:
    """
    Extract the file extension from a filename.

    Args:
        filename: The filename to extract extension from

    Returns:
        File extension without the dot, or empty string if no extension
    """
    if "." in filename:
        return filename.rsplit(".", 1)[1].lower()
    return ""


def generate_presigned_post(
    bucket_name: str, s3_key: str, file_name: str
) -> Dict[str, Any]:
    """
    Generate a presigned POST for uploading a file to S3.

    Args:
        bucket_name: The S3 bucket name
        s3_key: The S3 key (path) where the file will be stored
        file_name: The original file name

    Returns:
        Dictionary containing presigned POST URL and fields
    """
    s3_client = boto3.client("s3")

    # Set content type based on file extension
    content_type = get_content_type(file_name)

    # Generate presigned POST with 1 hour expiration
    presigned_post = s3_client.generate_presigned_post(
        Bucket=bucket_name,
        Key=s3_key,
        Fields={"Content-Type": content_type},
        Conditions=[
            {"Content-Type": content_type}
            # Removed content-length-range to avoid size restriction issues
        ],
        ExpiresIn=3600,  # 1 hour
    )

    return presigned_post


def get_content_type(filename: str) -> str:
    """
    Determine the content type based on file extension.

    Args:
        filename: The filename to analyze

    Returns:
        Content type string
    """
    import mimetypes

    # Get content type from file extension
    content_type, _ = mimetypes.guess_type(filename)

    # Default to binary if content type cannot be determined
    if content_type is None:
        content_type = "application/octet-stream"

    return content_type
