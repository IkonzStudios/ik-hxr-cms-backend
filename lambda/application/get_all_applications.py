import json
import os
from typing import Dict, Any
from utils.helpers import (
    get_application_by_id_from_db,
    create_applications_list_response,
    create_error_response,
)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to get all applications for an organization from DynamoDB.

    Expected event structure:
    {
        "queryStringParameters": {
            "organization_id": "org-uuid"
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

        # Extract organization ID from query string
        query_parameters = event.get("queryStringParameters", {})
        org_id = query_parameters.get("organization_id") if query_parameters else None

        if not org_id:
            return create_error_response(400, "Organization ID is required")

        # Fetch all applications for the organization
        applications, get_error = get_application_by_id_from_db(org_id, table_name)
        if get_error:
            return get_error

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
