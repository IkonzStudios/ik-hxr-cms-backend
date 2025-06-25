import json
import os
from typing import Dict, Any
from utils.helpers import (
    parse_request_body,
    validate_required_fields,
    create_organization_data,
    save_organization_to_db,
    create_success_response,
    create_error_response,
)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to create a new organization in DynamoDB.

    Expected event structure:
    {
        "name": "Acme Corporation",
        "license": "LICENSE-12345-67890",
        "created_by": "system-admin",
        "updated_by": "system-admin"
    }
    """

    try:
        # Get table name from environment variable
        table_name = os.environ.get("ORGANIZATIONS_TABLE_NAME")
        if not table_name:
            raise ValueError("ORGANIZATIONS_TABLE_NAME environment variable not set")

        # Debug: Print the event structure
        print(f"Event: {json.dumps(event)}")

        # Parse request body
        body, parse_error = parse_request_body(event)
        if parse_error:
            return parse_error

        # Validate required fields
        validation_error = validate_required_fields(body)
        if validation_error:
            return validation_error

        # Create organization data
        organization_data = create_organization_data(body)

        # Save to database
        save_error = save_organization_to_db(organization_data, table_name)
        if save_error:
            return save_error

        # Return success response
        return create_success_response(organization_data)

    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        print(f"Error creating organization: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback

        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, "Internal server error")
