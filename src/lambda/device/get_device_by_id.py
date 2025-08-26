import json
import os
import traceback
from typing import Dict, Any

from utils.helpers import (
    get_device_by_id_from_db,
    create_enriched_device_response,
    create_error_response,
)
from utils.rbac import check_view_permission_with_org


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to get a device by ID from DynamoDB.

    Expected event structure:
    {
        "pathParameters": {
            "id": "device-uuid"
        },
        "requestContext": {
            "authorizer": {
                "user_id": "user-sub",
                "email": "user@example.com",
                "role": "admin",
                "organization_id": "org-123"
            }
        }
    }
    """

    try:
        # Get table name from environment variable
        table_name = os.environ.get("DEVICES_TABLE_NAME")
        if not table_name:
            raise ValueError("DEVICES_TABLE_NAME environment variable not set")

        # Debug: Print the event structure
        print(f"Event object: {json.dumps(event)}")

        # User context will be extracted by RBAC helper

        # Extract device ID from path parameters
        path_parameters = event.get("pathParameters", {})
        device_id = path_parameters.get("id") if path_parameters else None

        if not device_id:
            return create_error_response(400, "Device ID is required")

        # First get the device to check its organization_id
        device, get_error = get_device_by_id_from_db(device_id, table_name)
        if get_error:
            return get_error

        # RBAC: Check if user has permission to view devices in this organization
        rbac_error, user_info = check_view_permission_with_org(event, "device", device["organization_id"])
        if rbac_error:
            return rbac_error

        # Log user action for audit
        print(f"User {user_info['user_id']} ({user_info['role']}) viewing device {device_id}")

        # Return enriched success response
        return create_enriched_device_response(device)

    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        print(f"Error getting device: {str(e)}")
        print(f"Error type: {type(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, "Internal server error")
