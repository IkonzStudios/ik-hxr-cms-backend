import json
import os
from typing import Dict, Any
from utils.helpers import (
    parse_request_body,
    get_organization_by_id_from_db,
    prepare_update_data,
    update_organization_in_db,
    create_organization_response,
    create_error_response,
)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to update an organization by ID in DynamoDB.

    Expected event structure:
    {
        "pathParameters": {
            "id": "organization-uuid"
        },
        "body": {
            "name": "Updated Acme Corporation",
            "license": "LICENSE-12345-67890-UPDATED",
            "updated_by": "user-admin-456"
        }
    }
    """

    try:
        # Get table name from environment variable
        table_name = os.environ.get("ORGANIZATIONS_TABLE_NAME")
        if not table_name:
            raise ValueError("ORGANIZATIONS_TABLE_NAME environment variable not set")

        # Debug: Print the event structure
        print(f"Event: {json.dumps(event)}")

        # Extract organization ID from path parameters
        path_parameters = event.get("pathParameters", {})
        organization_id = path_parameters.get("id") if path_parameters else None

        if not organization_id:
            return create_error_response(400, "Organization ID is required")

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

        # Update organization in database
        update_error = update_organization_in_db(
            organization_id, update_data, table_name
        )
        if update_error:
            return update_error

        # Get updated organization to return in response
        updated_organization, get_error = get_organization_by_id_from_db(
            organization_id, table_name
        )
        if get_error:
            return get_error

        # Return success response
        return create_organization_response(updated_organization)

    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        print(f"Error updating organization: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback

        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, "Internal server error")
