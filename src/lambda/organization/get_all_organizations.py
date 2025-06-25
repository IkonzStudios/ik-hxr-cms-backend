import json
import os
from typing import Dict, Any
from utils.helpers import (
    get_all_organizations_from_db,
    create_organizations_list_response,
    create_error_response,
)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to get all organizations from DynamoDB.

    Expected event structure:
    {
        // No path parameters needed
    }
    """

    try:
        # Get table name from environment variable
        table_name = os.environ.get("ORGANIZATIONS_TABLE_NAME")
        if not table_name:
            raise ValueError("ORGANIZATIONS_TABLE_NAME environment variable not set")

        # Debug: Print the event structure
        print(f"Event: {json.dumps(event)}")

        # Get organizations from database
        organizations, get_error = get_all_organizations_from_db(table_name)
        if get_error:
            return get_error

        # Return success response
        return create_organizations_list_response(organizations)

    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        print(f"Error getting all organizations: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback

        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, "Internal server error")
