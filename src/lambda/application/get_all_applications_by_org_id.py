import json
import os
from typing import Dict, Any
from utils.helpers import (
    get_applications_by_org_id_from_db,
    create_applications_list_response,
    create_error_response,
)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to get all applications by organization ID from DynamoDB.

    Expected event structure:
    {
        "pathParameters": {
            "orgId": "123e4567-e89b-12d3-a456-426614174000"
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

        # Get organization ID from path parameters
        path_parameters = event.get("pathParameters", {})
        org_id = path_parameters.get("orgId")

        if not org_id:
            return create_error_response(400, "Organization ID is required")

        # Get applications from database
        applications, error = get_applications_by_org_id_from_db(org_id, table_name)
        if error:
            return error

        # Return success response
        return create_applications_list_response(applications)

    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        print(f"Error getting applications: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback

        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, "Internal server error")
