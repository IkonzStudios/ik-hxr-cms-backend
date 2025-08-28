import json
import os
import traceback
from typing import Dict, Any

from utils.helpers import (
    parse_request_body,
    validate_required_fields,
    create_device_data,
    save_device_to_db,
    create_success_response,
    create_error_response,
)
from utils.rbac import check_create_permission_with_org


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to create a new device in DynamoDB.

    Expected event structure:
    {
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "name": "Device Name",
        "description": "Device Description",
        "organization_id": "123e4567-e89b-12d3-a456-426614174000",
        "model": "Device Model",
        "version": "1.0.0",
        "ip_address": "192.168.1.100",
        "playlists": "[\"playlist1\", \"playlist2\"]",
        "applications": "[\"app1\", \"app2\"]",
        "contents_initiated": "[]",
        "contents_downloading": "[]",
        "contents_downloaded": "[]",
        "status": "active",
        "storage_left": 100.5,
        "storage_consumed": 50.2
    }
    """

    try:
        # Get table name from environment variable
        table_name = os.environ.get("DEVICES_TABLE_NAME")
        if not table_name:
            raise ValueError("DEVICES_TABLE_NAME environment variable not set")

        # Debug: Print the event structure
        print(f"Event: {json.dumps(event)}")

        # Parse request body first to get organization_id for RBAC check
        body, parse_error = parse_request_body(event)
        if parse_error:
            return parse_error

        # Extract organization_id from request body for RBAC validation
        organization_id = body.get("organization_id", "")
        if not organization_id:
            return create_error_response(400, "organization_id is required")

        # RBAC: Check if user has permission to create devices in this organization
        rbac_error, user_info = check_create_permission_with_org(event, "device", organization_id)
        if rbac_error:
            return rbac_error

        # Log user action for audit
        print(f"User {user_info['user_id']} ({user_info['role']}) creating device in org {organization_id}")

        # Validate required fields
        validation_error = validate_required_fields(body)
        if validation_error:
            return validation_error

        # Create device data
        device_data = create_device_data(body)

        # Save to database
        save_error = save_device_to_db(device_data, table_name)
        if save_error:
            return save_error

        # Return success response
        return create_success_response(device_data)

    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        print(f"Error creating device: {str(e)}")
        print(f"Error type: {type(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, "Internal server error")
