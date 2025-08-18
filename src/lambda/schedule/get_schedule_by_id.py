import json
import os
from typing import Dict, Any
from utils.helpers import (
    get_schedule_by_id_from_db,
    create_schedule_response,
    create_error_response,
)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to get a schedule by ID from DynamoDB.

    Expected event structure:
    {
        "pathParameters": {
            "id": "schedule-uuid"
        }
    }
    """

    try:
        # Get table name from environment variable
        table_name = os.environ.get("SCHEDULES_TABLE_NAME")
        if not table_name:
            raise ValueError("SCHEDULES_TABLE_NAME environment variable not set")

        # Debug: Print the event structure
        print(f"Event: {json.dumps(event)}")

        # Extract schedule ID from path parameters
        path_parameters = event.get("pathParameters", {})
        schedule_id = path_parameters.get("id") if path_parameters else None

        if not schedule_id:
            return create_error_response(400, "Schedule ID is required")

        # Get schedule from database
        schedule, get_error = get_schedule_by_id_from_db(schedule_id, table_name)
        if get_error:
            return get_error

        # Return success response
        return create_schedule_response(schedule)

    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        print(f"Error getting schedule: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback

        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, "Internal server error")
