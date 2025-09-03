import json
import os
import traceback
from typing import Dict, Any

from utils.helpers import (
    parse_request_body,
    get_device_by_id_from_db,
    create_device_response,
    create_error_response,
    update_device_in_db,
)
from iot.remove_content import remove_content_from_device_utility
from utils.rbac import check_edit_permission_with_org
from utils.constants import HTTP_STATUS_CODES, DEVICE_ERROR_MESSAGES, DEVICE_SUCCESS_MESSAGES


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to remove content from a device.

    Expected event structure:
    {
        "pathParameters": {
            "id": "device-uuid"
        },
        "body": {
            "content_ids": ["content1", "content2"]
        }
    }
    """

    try:
        # Get table name from environment variable
        table_name = os.environ.get("DEVICES_TABLE_NAME")
        if not table_name:
            return create_error_response(500, DEVICE_ERROR_MESSAGES["MISSING_ENVIRONMENT_VAR"])

        # Debug: Print the event structure
        print(f"Event: {json.dumps(event)}")

        # Extract device ID from path parameters
        path_parameters = event.get("pathParameters", {})
        device_id = path_parameters.get("id") if path_parameters else None

        if not device_id:
            return create_error_response(400, DEVICE_ERROR_MESSAGES["DEVICE_ID_REQUIRED"])

        # First get the existing device to check its organization_id for RBAC
        existing_device, get_error = get_device_by_id_from_db(device_id, table_name)
        if get_error:
            return get_error

        # RBAC: Check if user has permission to edit devices in this organization
        rbac_error, user_info = check_edit_permission_with_org(event, "device", existing_device["organization_id"])
        if rbac_error:
            return rbac_error

        # Log user action for audit
        print(f"User {user_info['user_id']} ({user_info['role']}) removing content from device {device_id}")

        # Parse request body
        body, parse_error = parse_request_body(event)
        if parse_error:
            return parse_error

        # Check if body has content_ids
        if not body:
            return create_error_response(400, DEVICE_ERROR_MESSAGES["EMPTY_REQUEST_BODY"])

        content_ids = body.get("content_ids")
        if not content_ids:
            return create_error_response(400, DEVICE_ERROR_MESSAGES["INVALID_CONTENT_IDS"])

        if not isinstance(content_ids, list):
            return create_error_response(400, DEVICE_ERROR_MESSAGES["INVALID_CONTENT_IDS"])

        # Validate content IDs are strings
        for content_id in content_ids:
            if not isinstance(content_id, str) or not content_id.strip():
                return create_error_response(400, DEVICE_ERROR_MESSAGES["INVALID_CONTENT_IDS"])

        # Store original device state for rollback
        original_contents_initiated = existing_device.get("contents_initiated", [])
        original_contents_downloading = existing_device.get("contents_downloading", [])
        original_contents_downloaded = existing_device.get("contents_downloaded", [])
        
        if isinstance(original_contents_initiated, str):
            original_contents_initiated = json.loads(original_contents_initiated) if original_contents_initiated else []
        if isinstance(original_contents_downloading, str):
            original_contents_downloading = json.loads(original_contents_downloading) if original_contents_downloading else []
        if isinstance(original_contents_downloaded, str):
            original_contents_downloaded = json.loads(original_contents_downloaded) if original_contents_downloaded else []

        # Get environment variables for IoT API call
        contents_table_name = os.environ.get("CONTENTS_TABLE_NAME")
        content_bucket_name = os.environ.get("CONTENT_BUCKET_NAME")
        
        if not contents_table_name:
            return create_error_response(500, "CONTENTS_TABLE_NAME environment variable not set")
        if not content_bucket_name:
            return create_error_response(500, "CONTENT_BUCKET_NAME environment variable not set")
        
        # Call IoT API to remove content from device
        success, error_msg, iot_response = remove_content_from_device_utility(
            device_id=device_id,
            content_ids=content_ids,
            contents_table_name=contents_table_name,
            content_bucket_name=content_bucket_name,
            devices_table_name=table_name
        )
        
        if not success:
            return create_error_response(502, f"IoT API error: {error_msg}")
        
        database_updated = False
        
        try:
            # Update device's content arrays in database by removing specified content IDs
            current_contents_initiated = existing_device.get("contents_initiated", [])
            current_contents_downloading = existing_device.get("contents_downloading", [])
            current_contents_downloaded = existing_device.get("contents_downloaded", [])
            
            if isinstance(current_contents_initiated, str):
                current_contents_initiated = json.loads(current_contents_initiated) if current_contents_initiated else []
            if isinstance(current_contents_downloading, str):
                current_contents_downloading = json.loads(current_contents_downloading) if current_contents_downloading else []
            if isinstance(current_contents_downloaded, str):
                current_contents_downloaded = json.loads(current_contents_downloaded) if current_contents_downloaded else []
            
            # Check if content IDs exist in any of the content arrays
            all_content_ids = current_contents_initiated + current_contents_downloading + current_contents_downloaded
            content_ids_to_remove = [cid for cid in content_ids if cid in all_content_ids]
            if not content_ids_to_remove:
                return create_error_response(400, "None of the specified content IDs are currently assigned to this device")
            
            # Remove specified content IDs from all content arrays
            updated_contents_initiated = [content for content in current_contents_initiated if content not in content_ids]
            updated_contents_downloading = [content for content in current_contents_downloading if content not in content_ids]
            updated_contents_downloaded = [content for content in current_contents_downloaded if content not in content_ids]
            
            update_data = {
                "contents_initiated": updated_contents_initiated,
                "contents_downloading": updated_contents_downloading,
                "contents_downloaded": updated_contents_downloaded,
            }
            
            update_error = update_device_in_db(device_id, update_data, table_name)
            if update_error:
                return update_error
            
            database_updated = True
                
            # Get updated device to return in response
            updated_device, get_error = get_device_by_id_from_db(device_id, table_name)
            if get_error:
                updated_device = existing_device  # Fallback to existing device
            
            # Create success result for response
            content_removal_result = {
                "success": True,
                "message": DEVICE_SUCCESS_MESSAGES['CONTENT_REMOVED'],
                "removed_content_ids": content_ids_to_remove,
                "remaining_contents": len(updated_contents_initiated + updated_contents_downloading + updated_contents_downloaded),
                "iot_response": iot_response
            }
            
            print(f"Content removal successful for device {device_id}")
            print(f"IoT API response: {json.dumps(iot_response, indent=2)}")
            
            return create_device_response(updated_device, {"content_removal": content_removal_result})
                
        except Exception as e:
            print(f"Error during content removal: {str(e)}")
            
            # Rollback database changes if they were made
            if database_updated:
                try:
                    print("Rolling back database changes due to error")
                    rollback_data = {
                        "contents_initiated": original_contents_initiated,
                        "contents_downloading": original_contents_downloading,
                        "contents_downloaded": original_contents_downloaded,
                    }
                    update_device_in_db(device_id, rollback_data, table_name)
                    print("Database rollback successful")
                except Exception as rollback_error:
                    print(f"Database rollback failed: {str(rollback_error)}")
            
            return create_error_response(500, f"Content removal failed: {str(e)}")

    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        print(f"Error removing content from device: {str(e)}")
        print(f"Error type: {type(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, HTTP_STATUS_CODES[500])
