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
from utils.rbac import check_edit_permission_with_org
from utils.constants import HTTP_STATUS_CODES, DEVICE_ERROR_MESSAGES, DEVICE_SUCCESS_MESSAGES
from iot.assign_content import assign_content_to_device_utility


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to assign content to a device.

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
        print(f"User {user_info['user_id']} ({user_info['role']}) assigning content to device {device_id}")

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
        original_contents = existing_device.get("contents", [])
        if isinstance(original_contents, str):
            original_contents = json.loads(original_contents) if original_contents else []

        # Trigger IoT content assignment
        iot_assignment_result = None
        database_updated = False
        
        try:
            # Call IoT utility function
            
            # Get required environment variables
            contents_table_name = os.environ.get("CONTENTS_TABLE_NAME")
            content_bucket_name = os.environ.get("CONTENT_BUCKET_NAME")
            
            if contents_table_name and content_bucket_name:
                print(f"Triggering IoT content assignment for device {device_id}")
                
                success, error_msg, iot_response = assign_content_to_device_utility(
                    device_id=device_id,
                    content_ids=content_ids,
                    contents_table_name=contents_table_name,
                    content_bucket_name=content_bucket_name,
                    devices_table_name=table_name
                )
                
                iot_assignment_result = {
                    "success": success,
                    "error": error_msg,
                    "response": iot_response
                }
                
                if success:
                    print(f"IoT content assignment successful for device {device_id}")
                    
                    # Update device's content list in database
                    current_contents = existing_device.get("contents", [])
                    if isinstance(current_contents, str):
                        current_contents = json.loads(current_contents) if current_contents else []
                    
                    # Add new content IDs to existing ones (avoid duplicates)
                    updated_contents = list(set(current_contents + content_ids))
                    update_data = {"contents": updated_contents}
                    
                    update_error = update_device_in_db(device_id, update_data, table_name)
                    if update_error:
                        print(f"Database update failed after successful IoT assignment: {update_error}")
                        # TODO: Implement IoT rollback when rollback API becomes available
                        return update_error
                    
                    database_updated = True
                        
                    # Get updated device to return in response
                    updated_device, get_error = get_device_by_id_from_db(device_id, table_name)
                    if get_error:
                        updated_device = existing_device  # Fallback to existing device
                    
                    return create_device_response(updated_device, iot_assignment_result)
                else:
                    print(f"IoT content assignment failed for device {device_id}: {error_msg}")
                    return create_error_response(502, f"{DEVICE_ERROR_MESSAGES['ASSIGNMENT_FAILED']}: {error_msg}")
            else:
                print("IoT content assignment skipped: missing CONTENTS_TABLE_NAME or CONTENT_BUCKET_NAME")
                return create_error_response(500, DEVICE_ERROR_MESSAGES["MISSING_ENVIRONMENT_VAR"])
                
        except Exception as e:
            print(f"Error during IoT content assignment: {str(e)}")
            
            # Rollback database changes if they were made
            if database_updated:
                try:
                    print("Rolling back database changes due to error")
                    rollback_data = {"contents": original_contents}
                    update_device_in_db(device_id, rollback_data, table_name)
                    print("Database rollback successful")
                except Exception as rollback_error:
                    print(f"Database rollback failed: {str(rollback_error)}")
            
            return create_error_response(500, f"{DEVICE_ERROR_MESSAGES['IOT_API_ERROR']}: {str(e)}")

    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        print(f"Error assigning content to device: {str(e)}")
        print(f"Error type: {type(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, HTTP_STATUS_CODES[500])
