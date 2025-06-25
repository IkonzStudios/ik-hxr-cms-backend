import json
import os
from typing import Dict, Any
from utils.helpers import (
    get_user_by_id_from_db,
    create_user_response,
    create_error_response,
)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to get a user by ID from DynamoDB.

    Expected event structure:
    {
        "pathParameters": {
            "id": "user-uuid"
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

        # Get user from database
        user, get_error = get_user_by_id_from_db(user_id, table_name)
        if get_error:
            return get_error

        # Return success response
        return create_user_response(user)

    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        print(f"Error getting user: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback

        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, "Internal server error")
