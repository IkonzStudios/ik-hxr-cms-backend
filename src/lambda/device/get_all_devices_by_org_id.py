import json
import os
from typing import Dict, Any
from utils.helpers import (
    get_devices_by_org_id_from_db,
    create_devices_list_response,
    create_error_response,
)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to get all devices by organization ID from DynamoDB.

    Expected event structure:
    {
        "pathParameters": {
            "orgId": "organization-uuid"
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

        # Extract organization ID from path parameters
        path_parameters = event.get("pathParameters", {})
        org_id = path_parameters.get("orgId") if path_parameters else None

        if not org_id:
            return create_error_response(400, "Organization ID is required")

        # Get devices from database
        devices, get_error = get_devices_by_org_id_from_db(org_id, table_name)
        if get_error:
            return get_error

        # Return success response
        return create_devices_list_response(devices)

    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        print(f"Error getting devices by organization ID: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback

        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, "Internal server error")
