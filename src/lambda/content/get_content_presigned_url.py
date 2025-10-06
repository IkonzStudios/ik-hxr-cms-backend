import json
import os
import boto3
from typing import Dict, Any
from botocore.exceptions import ClientError
from botocore.config import Config

from utils.helpers import (
    get_cors_headers,
    create_error_response,
    parse_request_body,
)
from utils.rbac import check_view_permission_with_org


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to generate a presigned URL for content viewing.

    Expected request body:
    {
        "key": "contents/73ffc2ad-1551-49fa-864c-133a60e9e2ef/7fbcb394-7546-459c-ae59-3468ae77c449.mp4"
    }

    The organization_id is extracted from the key path (second segment after "contents/").

    Returns:
    - 200: Success with presigned URL
    - 400: Bad request (missing or invalid key format)
    - 403: Forbidden (user doesn't have permission)
    - 500: Internal server error
    """

    try:
        # Get S3 bucket name from environment variable
        bucket_name = os.environ.get("CONTENT_BUCKET_NAME")
        if not bucket_name:
            print("Error: CONTENT_BUCKET_NAME environment variable not set")
            return create_error_response(500, "Content bucket configuration missing")

        # Debug: Print the event structure
        print(f"Event: {json.dumps(event)}")

        # Parse request body
        body, parse_error = parse_request_body(event)
        if parse_error:
            return parse_error

        # Extract the S3 key from request body
        s3_key = body.get("key")

        # Validate the S3 key parameter
        if not s3_key:
            return create_error_response(400, "Missing required parameter: key")

        # Validate key format (basic validation)
        if not s3_key.strip():
            return create_error_response(400, "Invalid key: key cannot be empty")

        # Additional security: ensure key starts with contents/ to prevent accessing other files
        if not s3_key.startswith("contents/") and not s3_key.startswith("base-contents/"):
            return create_error_response(400, "Invalid key: key must start with 'contents/' or 'base-contents/'")

        # Extract organization_id from the key path
        # Expected format: "contents/73ffc2ad-1551-49fa-864c-133a60e9e2ef/7fbcb394-7546-459c-ae59-3468ae77c449.mp4"
        try:
            key_parts = s3_key.split("/")
            if len(key_parts) < 3 or key_parts[0] != "contents" and key_parts[0] != "base-contents":
                return create_error_response(400, "Invalid key format: expected 'contents/{org_id}/{file}'")
            
            organization_id = key_parts[1]
            if not organization_id:
                return create_error_response(400, "Invalid key: organization ID not found in path")
        except Exception as e:
            print(f"Error parsing organization_id from key: {str(e)}")
            return create_error_response(400, "Invalid key format")


        if s3_key.startswith("base-contents/"):
            rbac_error_base, user_info_base = check_view_permission_with_org(event, "base-content", organization_id)
            if rbac_error_base:
                return rbac_error_base
            else:
                print(f"User {user_info_base['user_id']} ({user_info_base['role']}) requesting presigned URL for org {organization_id}")
        else:
        # RBAC: Check if user has permission to view content in this organization
            rbac_error, user_info = check_view_permission_with_org(event, "content", organization_id)
            if rbac_error:
                return rbac_error
            else:
                print(f"User {user_info['user_id']} ({user_info['role']}) requesting presigned URL for org {organization_id}")

        # Generate presigned URL for viewing (GET operation)
        s3_client = boto3.client("s3")
        
        try:
            presigned_url = s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket_name, "Key": s3_key},
                ExpiresIn=3600,  # URL expires in 1 hour
            )
        except ClientError as e:
            print(f"Error generating presigned URL: {str(e)}")
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            
            if error_code == "NoSuchBucket":
                return create_error_response(500, "Content storage not configured properly")
            elif error_code == "NoSuchKey":
                return create_error_response(404, "Content not found")
            else:
                return create_error_response(500, "Failed to generate content access URL")

        # Log successful URL generation
        print(f"Generated presigned URL for key: {s3_key}")

        # Return success response with presigned URL
        return {
            "statusCode": 200,
            "headers": get_cors_headers(),
            "body": json.dumps({
                "message": "Presigned URL generated successfully",
                "presigned_url": presigned_url,
                "key": s3_key,
                "expires_in": 3600,
            }),
        }

    except Exception as e:
        print(f"Error generating presigned URL: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, "Internal server error")
