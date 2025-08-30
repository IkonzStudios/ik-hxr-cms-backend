import json
import os
import traceback
from typing import Dict, Any

from utils.helpers import (
    parse_request_body,
    get_device_by_id_from_db,
    prepare_update_data,
    update_device_in_db,
    create_device_response,
    create_error_response,
)
from utils.rbac import check_edit_permission_with_org
from iot.assign_content import assign_content_to_device_utility

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to update a device by ID in DynamoDB.

    Expected event structure:
    {
        "pathParameters": {
            "id": "device-uuid"
        },
        "body": {
            "name": "Updated Device Name",
            "description": "Updated Description",
            "model": "Updated Model",
            "version": "2.0.0",
            "ip_address": "192.168.1.101",
            "playlists": "[\"updated_playlist1\"]",
            "applications": "[\"updated_app1\"]",
            "contents_initiated": "[\"updated_content1\"]",
            "contents_downloading": "[]",
            "contents_downloaded": "[]",
            "status": "inactive",
            "storage_left": 80.0,
            "storage_consumed": 70.0
        }
    }
    """

    try:
        # Get table name from environment variable
        table_name = os.environ.get("DEVICES_TABLE_NAME")
        if not table_name:
            raise ValueError("DEVICES_TABLE_NAME environment variable not set")

        # Debug: Print the event structure
        print(f"Event: {json.dumps(event)}")

        # Extract device ID from path parameters
        path_parameters = event.get("pathParameters", {})
        device_id = path_parameters.get("id") if path_parameters else None

        if not device_id:
            return create_error_response(400, "Device ID is required")

        # First get the existing device to check its organization_id for RBAC
        existing_device, get_error = get_device_by_id_from_db(device_id, table_name)
        if get_error:
            return get_error

        # RBAC: Check if user has permission to edit devices in this organization
        rbac_error, user_info = check_edit_permission_with_org(event, "device", existing_device["organization_id"])
        if rbac_error:
            return rbac_error

        # Log user action for audit
        print(f"User {user_info['user_id']} ({user_info['role']}) updating device {device_id}")

        # Parse request body
        body, parse_error = parse_request_body(event)
        if parse_error:
            return parse_error

        # Check if body has any updateable fields
        if not body:
            return create_error_response(400, "Request body cannot be empty")

        # Prepare update data
        update_data = prepare_update_data(body)

        if not update_data:
            return create_error_response(400, "No valid fields to update")

        # Update device in database
        update_error = update_device_in_db(device_id, update_data, table_name)
        if update_error:
            return update_error

        # Get updated device to return in response
        updated_device, get_error = get_device_by_id_from_db(device_id, table_name)
        if get_error:
            return get_error

        # Check if contents were updated and trigger IoT content assignment
        iot_assignment_result = None
        if "contents_initiated" in update_data and update_data["contents_initiated"]:
            try:
              
                # Get required environment variables
                contents_table_name = os.environ.get("CONTENTS_TABLE_NAME")
                content_bucket_name = os.environ.get("CONTENT_BUCKET_NAME")
                
                if contents_table_name and content_bucket_name:
                    print(f"Triggering IoT content assignment for device {device_id}")
                    
                    # Parse contents JSON string to get content IDs
                    content_ids = json.loads(update_data["contents_initiated"]) if isinstance(update_data["contents_initiated"], str) else update_data["contents_initiated"]
                    
                    # Only proceed if content_ids has length
                    if content_ids and len(content_ids) > 0:
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
                        else:
                            print(f"IoT content assignment failed for device {device_id}: {error_msg}")
                    else:
                        print("IoT content assignment skipped: no content IDs to assign")
                else:
                    print("IoT content assignment skipped: missing CONTENTS_TABLE_NAME or CONTENT_BUCKET_NAME")
                    
            except Exception as e:
                print(f"Error during IoT content assignment: {str(e)}")
                iot_assignment_result = {
                    "success": False,
                    "error": f"IoT integration error: {str(e)}",
                    "response": None
                }

        # Return success response using the enhanced create_device_response function
        return create_device_response(updated_device, iot_assignment_result)

    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        print(f"Error updating device: {str(e)}")
        print(f"Error type: {type(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, "Internal server error")
