import json
import os
from typing import Dict, Any
from utils.helpers import (
    parse_request_body,
    get_schedule_by_id_from_db,
    prepare_update_data,
    validate_datetime_format,
    validate_schedule_times,
    update_schedule_in_db,
    create_schedule_response,
    create_error_response,
)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to update a schedule by ID in DynamoDB.

    Expected event structure:
    {
        "pathParameters": {
            "id": "schedule-uuid"
        },
        "body": {
            "start_at": "2024-01-15T09:00:00Z",
            "end_at": "2024-01-15T19:00:00Z",
            "loop": false,
            "is_active": false,
            "assigned_to": "[\"device-id-3\"]",
            "contents": "[\"content-id-3\", \"content-id-4\"]",
            "playlists": "[\"playlist-id-2\"]",
            "updated_by": "user-id-456"
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

        # Parse request body
        body, parse_error = parse_request_body(event)
        if parse_error:
            return parse_error

        # Check if body has any updateable fields
        if not body:
            return create_error_response(400, "Request body cannot be empty")

        # Validate datetime formats if provided
        for field in ["start_at", "end_at"]:
            if field in body:
                datetime_error = validate_datetime_format(body[field], field)
                if datetime_error:
                    return datetime_error

        # Validate schedule times if both are provided
        if "start_at" in body and "end_at" in body:
            schedule_time_error = validate_schedule_times(body)
            if schedule_time_error:
                return schedule_time_error

        # Prepare update data
        update_data = prepare_update_data(body)

        if not update_data:
            return create_error_response(400, "No valid fields to update")

        # Update schedule in database
        update_error = update_schedule_in_db(schedule_id, update_data, table_name)
        if update_error:
            return update_error

        # Get updated schedule to return in response
        updated_schedule, get_error = get_schedule_by_id_from_db(
            schedule_id, table_name
        )
        if get_error:
            return get_error

        # Return success response
        return create_schedule_response(updated_schedule)

    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        print(f"Error updating schedule: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback

        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, "Internal server error")
