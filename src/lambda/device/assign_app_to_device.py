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


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to assign application to a device.

    Expected event structure:
    {
        "pathParameters": {
            "id": "device-uuid"
        },
        "body": {
            "application_ids": ["app1", "app2"]
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
        print(f"User {user_info['user_id']} ({user_info['role']}) assigning application to device {device_id}")

        # Parse request body
        body, parse_error = parse_request_body(event)
        if parse_error:
            return parse_error

        # Check if body has application_ids
        if not body:
            return create_error_response(400, DEVICE_ERROR_MESSAGES["EMPTY_REQUEST_BODY"])

        application_ids = body.get("application_ids")
        if not application_ids:
            return create_error_response(400, DEVICE_ERROR_MESSAGES["INVALID_APPLICATION_IDS"])

        if not isinstance(application_ids, list):
            return create_error_response(400, DEVICE_ERROR_MESSAGES["INVALID_APPLICATION_IDS"])

        # Validate application IDs are strings
        for application_id in application_ids:
            if not isinstance(application_id, str) or not application_id.strip():
                return create_error_response(400, DEVICE_ERROR_MESSAGES["INVALID_APPLICATION_IDS"])

        # Store original device state for rollback
        original_applications = existing_device.get("applications", [])
        if isinstance(original_applications, str):
            original_applications = json.loads(original_applications) if original_applications else []

        # TODO: Implement IoT application assignment when IoT API becomes available
        # The IoT service doesn't currently have an API for assigning applications to devices
        # This functionality will need to be implemented when the IoT API is extended
        # Expected IoT API call:
        # success, error_msg, iot_response = assign_application_to_device_utility(
        #     device_id=device_id,
        #     application_ids=application_ids,
        #     applications_table_name=applications_table_name,
        #     devices_table_name=table_name
        # )
        
        database_updated = False
        
        try:
            # Update device's application list in database
            current_applications = existing_device.get("applications", [])
            if isinstance(current_applications, str):
                current_applications = json.loads(current_applications) if current_applications else []
            
            # Add new application IDs to existing ones (avoid duplicates)
            updated_applications = list(set(current_applications + application_ids))
            update_data = {"applications": updated_applications}
            
            update_error = update_device_in_db(device_id, update_data, table_name)
            if update_error:
                return update_error
            
            database_updated = True
                
            # Get updated device to return in response
            updated_device, get_error = get_device_by_id_from_db(device_id, table_name)
            if get_error:
                updated_device = existing_device  # Fallback to existing device
            
            # Create success result for response
            application_assignment_result = {
                "success": True,
                "message": f"{DEVICE_SUCCESS_MESSAGES['APPLICATION_ASSIGNED']} (Database updated only)",
                "assigned_application_ids": application_ids,
                "total_applications": len(updated_applications),
                "warning": "IoT device application assignment not yet implemented. Only database was updated."
            }
            
            print(f"Application assignment successful for device {device_id}")
            print("TODO: Implement IoT application assignment when API becomes available")
            
            return create_device_response(updated_device, {"application_assignment": application_assignment_result})
                
        except Exception as e:
            print(f"Error during application assignment: {str(e)}")
            
            # Rollback database changes if they were made
            if database_updated:
                try:
                    print("Rolling back database changes due to error")
                    rollback_data = {"applications": original_applications}
                    update_device_in_db(device_id, rollback_data, table_name)
                    print("Database rollback successful")
                except Exception as rollback_error:
                    print(f"Database rollback failed: {str(rollback_error)}")
            
            return create_error_response(500, f"{DEVICE_ERROR_MESSAGES['ASSIGNMENT_FAILED']}: {str(e)}")

    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        print(f"Error assigning application to device: {str(e)}")
        print(f"Error type: {type(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, HTTP_STATUS_CODES[500])
