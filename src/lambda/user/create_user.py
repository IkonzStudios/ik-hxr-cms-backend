import json
import os
from typing import Dict, Any
from utils.helpers import (
    parse_request_body,
    validate_required_fields,
    validate_email_format,
    validate_password_strength,
    validate_user_role,
    create_user_data,
    save_user_to_db,
    create_success_response,
    create_error_response,
)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to create a new user in DynamoDB.

    Expected event structure:
    {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "role": "manager",
        "password": "SecurePass123",
        "organization_id": "123e4567-e89b-12d3-a456-426614174000",
        "created_by": "user-admin-123",
        "updated_by": "user-admin-123"
    }
    """

    try:
        # Get table name from environment variable
        table_name = os.environ.get("USERS_TABLE_NAME")
        if not table_name:
            raise ValueError("USERS_TABLE_NAME environment variable not set")

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

        # Validate email format
        email_error = validate_email_format(body["email"])
        if email_error:
            return email_error

        # Validate password strength
        password_error = validate_password_strength(body["password"])
        if password_error:
            return password_error

        # Validate user role
        role_error = validate_user_role(body["role"])
        if role_error:
            return role_error

        # Create user data
        user_data = create_user_data(body)

        # Save to database
        save_error = save_user_to_db(user_data, table_name)
        if save_error:
            return save_error

        # Return success response
        return create_success_response(user_data)

    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        print(f"Error creating user: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback

        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, "Internal server error")
