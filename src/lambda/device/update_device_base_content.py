import json
import os
import boto3
from typing import Dict, Any
from datetime import datetime
from utils.rbac import check_edit_permission_with_org
from utils.helpers import get_cors_headers, parse_request_body, get_device_by_id_from_db, update_device_in_db
from iot.update_base_content import update_device_base_content_utility


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to update the base_content field of a device.

    Expected event structure:
    {
        "pathParameters": {
            "device_id": "device-123"
        },
        "body": {
            "base_content": "base-contents/73ffc2ad-1551-49fa-864c-133a60e9e2ef/7fbcb394-7546-459c-ae59-3468ae77c449.mp4"
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
        table_name = os.environ.get("DEVICES_TABLE_NAME")
        if not table_name:
            return {
                "statusCode": 500,
                "headers": get_cors_headers(),
                "body": json.dumps({"error": "DEVICES_TABLE_NAME environment variable not set"}),
            }

        # Extract device ID from path parameters
        device_id = event.get("pathParameters", {}).get("id")
        if not device_id:
            return {
                "statusCode": 400,
                "headers": get_cors_headers(),
                "body": json.dumps({"error": "Device ID is required in path parameters"}),
            }

        # Parse request body
        body, parse_error = parse_request_body(event)
        if parse_error:
            return parse_error

        # Extract base_content from request body
        base_content_id = body.get("base_content_id")
        base_content = body.get("base_content")

        if not base_content:
            return {
                "statusCode": 400,
                "headers": get_cors_headers(),
                "body": json.dumps({"error": "base_content is required"}),
            }
        
        if not base_content_id:
            return {
                "statusCode": 400,
                "headers": get_cors_headers(),
                "body": json.dumps({"error": "base_content_id is required"}),
            }

        # Validate base_content format
        if not is_valid_base_content_path(base_content):
            return {
                "statusCode": 400,
                "headers": get_cors_headers(),
                "body": json.dumps({"error": "Invalid base_content path format. Must start with 'base-contents/'"}), 
            }

        # Get device information to extract organization_id
        device_info, device_error = get_device_by_id_from_db(device_id, table_name)
        if device_error:
            return device_error

        organization_id = device_info.get("organization_id")
        if not organization_id:
            return {
                "statusCode": 400,
                "headers": get_cors_headers(),
                "body": json.dumps({"error": "Device organization not found"}),
            }

        # RBAC: Check if user has permission to edit devices in this organization
        rbac_error, user_info = check_edit_permission_with_org(event, "device", organization_id)
        if rbac_error:
            return rbac_error

        # Log user action for audit
        print(f"User {user_info['user_id']} ({user_info['role']}) updating base_content for device {device_id} in org {organization_id}")

        # Prepare update data
        update_data = {
            "base_content_id": base_content_id,
            "base_content": base_content,
            "updated_by": user_info["user_id"]
        }

        # Update device in database
        update_error = update_device_in_db(device_id, update_data, table_name)
        if update_error:
            return update_error

        # Get updated device data
        updated_device, device_error = get_device_by_id_from_db(device_id, table_name)
        if device_error:
            return device_error

        # Trigger IoT base content update with fallback mechanism
        iot_update_result = None
        try:
            # Get required environment variables
            content_bucket_name = os.environ.get("CONTENT_BUCKET_NAME")
            
            if content_bucket_name:
                print(f"Triggering IoT base content update for device {device_id}")
                
                success, error_msg, iot_response = update_device_base_content_utility(
                    device_id=device_id,
                    base_content_s3_key=base_content,
                    content_bucket_name=content_bucket_name,
                    devices_table_name=table_name
                )
                
                iot_update_result = {
                    "success": success,
                    "error": error_msg,
                    "response": iot_response
                }
                
                if success:
                    print(f"IoT base content update successful for device {device_id}")
                else:
                    print(f"IoT base content update failed for device {device_id}: {error_msg}")
            else:
                print("IoT base content update skipped: missing CONTENT_BUCKET_NAME")
                
        except Exception as e:
            print(f"Error during IoT base content update: {str(e)}")
            iot_update_result = {
                "success": False,
                "error": f"IoT integration error: {str(e)}",
                "response": None
            }

        # Prepare response based on IoT result
        if iot_update_result and not iot_update_result.get("success", True):
            # Device update succeeded but IoT update failed - return partial success
            return {
                "statusCode": 207,  # Multi-status: partial success
                "headers": get_cors_headers(),
                "body": json.dumps(
                    {
                        "message": "Device base_content updated successfully but IoT update failed",
                        "device_id": device_id,
                        "base_content": base_content,
                        "updated_at": updated_device.get("last_updated"),
                        "warning": "Base content update to IoT device failed",
                        "iot_update": iot_update_result
                    }
                ),
            }
        else:
            # Normal success response
            response_body = {
                "message": "Device base_content updated successfully",
                "device_id": device_id,
                "base_content": base_content,
                "updated_at": updated_device.get("last_updated"),
            }
            
            # Add IoT result if available
            if iot_update_result and iot_update_result.get("success"):
                response_body["message"] = "Device base_content updated successfully with IoT update"
                response_body["iot_update"] = iot_update_result
            
            return {
                "statusCode": 200,
                "headers": get_cors_headers(),
                "body": json.dumps(response_body),
            }

    except Exception as e:
        print(f"Error updating device base_content: {str(e)}")
        return {
            "statusCode": 500,
            "headers": get_cors_headers(),
            "body": json.dumps({"error": "Internal server error"}),
        }


def is_valid_base_content_path(base_content_path: str) -> bool:
    """
    Validate base_content path format.

    Args:
        base_content_path: The base content path to validate

    Returns:
        True if path is valid, False otherwise
    """
    if not base_content_path or not isinstance(base_content_path, str):
        return False
    
    # Must start with "base-contents/"
    if not base_content_path.startswith("base-contents/"):
        return False
    
    # Must have at least organization_id and filename
    path_parts = base_content_path.split("/")
    if len(path_parts) < 3:
        return False
    
    return True
