import json
import os
from typing import Dict, Any
from utils.helpers import (
    get_device_by_id_from_db,
    create_device_response,
    create_error_response,
)


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

        # Extract user context from authorizer
        request_context = event.get("requestContext", {})
        authorizer = request_context.get("authorizer", {})

        user_id = authorizer.get("user_id")
        user_email = authorizer.get("email")
        user_role = authorizer.get("role")
        user_org_id = authorizer.get("organization_id")

        print(
            f"User Context - ID: {user_id}, Email: {user_email}, Role: {user_role}, Org: {user_org_id}"
        )

        # Extract device ID from path parameters
        path_parameters = event.get("pathParameters", {})
        device_id = path_parameters.get("id") if path_parameters else None

        if not device_id:
            return create_error_response(400, "Device ID is required")

        # Get device from database
        device, get_error = get_device_by_id_from_db(device_id, table_name)
        if get_error:
            return get_error

        # Return success response
        return create_device_response(device)

    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        print(f"Error getting device: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback

        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, "Internal server error")
