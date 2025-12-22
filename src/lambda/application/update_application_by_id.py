import json
import os
import sys
from typing import Dict, Any

from utils.helpers import (
    parse_request_body,
    validate_application_fields,
    prepare_update_data,
    update_application_in_db,
    get_application_by_id_from_db,
    create_application_response,
    create_error_response,
)
from utils.rbac import check_edit_permission_with_org


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to update an application by ID in DynamoDB.

    Expected event structure:
    {
        "pathParameters": {
            "id": "application-id-123"
        },
        "body": {
            "logo": "https://example.com/new-logo.png",
            "version": "1.1.0",
            "platform": "ios",
            "type": "RPM",
            "url": "https://example.com/new-app",
            "updated_by": "user-id-123"
        }
    }
    """

    try:
        # Get table name from environment variable
        table_name = os.environ.get("APPLICATIONS_TABLE_NAME")
        if not table_name:
            raise ValueError("APPLICATIONS_TABLE_NAME environment variable not set")

        # Debug: Print the event structure
        print(f"Event: {json.dumps(event)}")

        # Get application ID from path parameters
        path_parameters = event.get("pathParameters", {})
        application_id = path_parameters.get("id")

        if not application_id:
            return create_error_response(400, "Application ID is required")

        # First get the application to check its organization_id for RBAC
        existing_application, get_error = get_application_by_id_from_db(application_id, table_name)
        if get_error:
            return get_error

        # RBAC: Check if user has permission to edit applications in this organization
        rbac_error, user_info = check_edit_permission_with_org(event, "application", existing_application["organization_id"])
        if rbac_error:
            return rbac_error

        # Log user action for audit
        print(f"User {user_info['user_id']} ({user_info['role']}) updating application {application_id}")

        # Parse request body
        body, parse_error = parse_request_body(event)
        if parse_error:
            return parse_error

        # Validate application fields
        field_validation_error = validate_application_fields(body)
        if field_validation_error:
            return create_error_response(400, field_validation_error)

        # Prepare update data
        update_data = prepare_update_data(body)

        if not update_data:
            return create_error_response(400, "No valid fields to update")

        # Update application in database
        update_error = update_application_in_db(application_id, update_data, table_name)
        if update_error:
            return update_error

        # Get updated application
        application, error = get_application_by_id_from_db(application_id, table_name)
        if error:
            return error

        # Return success response
        return create_application_response(application)

    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        print(f"Error updating application: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback

        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, "Internal server error")
