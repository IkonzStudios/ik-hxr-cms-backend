import json
import os
from typing import Dict, Any
from utils.helpers import (
    parse_request_body,
    get_user_by_id_from_db,
    prepare_update_data,
    validate_email_format,
    validate_password_strength,
    validate_user_role,
    update_user_in_db,
    create_user_response,
    create_error_response,
)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to update a user by ID in DynamoDB.

    Expected event structure:
    {
        "pathParameters": {
            "id": "user-uuid"
        },
        "body": {
            "first_name": "John",
            "last_name": "Smith",
            "email": "john.smith@example.com",
            "role": "admin",
            "password": "NewSecurePass456",
            "updated_by": "user-admin-456"
        }
    }
    """

    try:
        # Get table name from environment variable
        table_name = os.environ.get("USERS_TABLE_NAME")
        if not table_name:
            raise ValueError("USERS_TABLE_NAME environment variable not set")

        # Debug: Print the event structure
        print(f"Event: {json.dumps(event)}")

        # Extract user ID from path parameters
        path_parameters = event.get("pathParameters", {})
        user_id = path_parameters.get("id") if path_parameters else None

        if not user_id:
            return create_error_response(400, "User ID is required")

        # Parse request body
        body, parse_error = parse_request_body(event)
        if parse_error:
            return parse_error

        # Check if body has any updateable fields
        if not body:
            return create_error_response(400, "Request body cannot be empty")

        # Validate email format if provided
        if "email" in body:
            email_error = validate_email_format(body["email"])
            if email_error:
                return email_error

        # Validate password strength if provided
        if "password" in body:
            password_error = validate_password_strength(body["password"])
            if password_error:
                return password_error

        # Validate user role if provided
        if "role" in body:
            role_error = validate_user_role(body["role"])
            if role_error:
                return role_error

        # Prepare update data
        update_data = prepare_update_data(body)

        if not update_data:
            return create_error_response(400, "No valid fields to update")

        # Update user in database
        update_error = update_user_in_db(user_id, update_data, table_name)
        if update_error:
            return update_error

        # Get updated user to return in response
        updated_user, get_error = get_user_by_id_from_db(user_id, table_name)
        if get_error:
            return get_error

        # Return success response
        return create_user_response(updated_user)

    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        print(f"Error updating user: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback

        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, "Internal server error")
