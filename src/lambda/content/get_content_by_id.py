import json
import os
from typing import Dict, Any
from utils.helpers import (
    get_content_by_id_from_db,
    create_content_response,
    create_error_response,
)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to get a content by ID from DynamoDB.

    Expected event structure:
    {
        "pathParameters": {
            "id": "content-uuid"
        }
    }
    """

    try:
        # Get table name from environment variable
        table_name = os.environ.get("CONTENTS_TABLE_NAME")
        if not table_name:
            raise ValueError("CONTENTS_TABLE_NAME environment variable not set")

        # Debug: Print the event structure
        print(f"Event: {json.dumps(event)}")

        # Extract content ID from path parameters
        path_parameters = event.get("pathParameters", {})
        content_id = path_parameters.get("id") if path_parameters else None

        if not content_id:
            return create_error_response(400, "Content ID is required")

        # Get content from database
        content, get_error = get_content_by_id_from_db(content_id, table_name)
        if get_error:
            return get_error

        # Return success response
        return create_content_response(content)

    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        print(f"Error getting content: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback

        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, "Internal server error")
