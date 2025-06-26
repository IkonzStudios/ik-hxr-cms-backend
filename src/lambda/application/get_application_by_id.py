import json
import os
from typing import Dict, Any
from utils.helpers import (
    get_application_by_id_from_db,
    create_application_response,
    create_error_response,
)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to get an application by ID from DynamoDB.

    Expected event structure:
    {
        "pathParameters": {
            "id": "application-uuid"
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

        # Extract application ID from path parameters
        path_parameters = event.get("pathParameters", {})
        application_id = path_parameters.get("id") if path_parameters else None

        if not application_id:
            return create_error_response(400, "Application ID is required")

        # Get application from database
        application, get_error = get_application_by_id_from_db(application_id, table_name)
        if get_error:
            return get_error

        # Return success response
        return create_application_response(application)

    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        print(f"Error getting application: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback

        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, "Internal server error")
