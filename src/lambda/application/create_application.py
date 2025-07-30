import json
import os
from typing import Dict, Any, Optional
from utils.helpers import (
    parse_request_body,
    validate_required_fields,
    validate_application_fields,
    create_application_data,
    save_application_to_db,
    create_success_response,
    create_error_response,
)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to create a new application in DynamoDB.

    Expected event structure:
    {
        "name": "My Application",
        "description": "Application description",
        "status": "active",
        "logo": "https://example.com/logo.png",
        "version": "1.0.0",
        "platform": "android",
        "organization_id": "123e4567-e89b-12d3-a456-426614174000",
        "created_by": "user-id-123",
        "updated_by": "user-id-123"
    }
    """

    try:
        # Get table name from environment variable
        table_name = os.environ.get("APPLICATIONS_TABLE_NAME")
        if not table_name:
            raise ValueError("APPLICATIONS_TABLE_NAME environment variable not set")

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

        # Validate application fields
        field_validation_error = validate_application_fields(body)
        if field_validation_error:
            return create_error_response(400, field_validation_error)

        # Create application data
        application_data = create_application_data(body)

        # Save to database
        save_error = save_application_to_db(application_data, table_name)
        if save_error:
            return save_error

        # Return success response
        return create_success_response(application_data)

    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        print(f"Error creating application: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback

        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, "Internal server error")
