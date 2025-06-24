import json
import os
from typing import Dict, Any
from utils.helpers import (
    parse_request_body,
    validate_required_fields,
    validate_datetime_format,
    validate_schedule_times,
    create_schedule_data,
    save_schedule_to_db,
    create_success_response,
    create_error_response,
)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to create a new schedule in DynamoDB.

    Expected event structure:
    {
        "start_at": "2024-01-15T10:00:00Z",
        "end_at": "2024-01-15T18:00:00Z",
        "loop": true,
        "is_active": true,
        "assigned_to": "[\"device-id-1\", \"device-id-2\"]",
        "contents": "[\"content-id-1\", \"content-id-2\"]",
        "playlists": "[\"playlist-id-1\"]",
        "organization_id": "123e4567-e89b-12d3-a456-426614174000",
        "created_by": "user-id-123",
        "updated_by": "user-id-123"
    }
    """

    try:
        # Get table name from environment variable
        table_name = os.environ.get("SCHEDULES_TABLE_NAME")
        if not table_name:
            raise ValueError("SCHEDULES_TABLE_NAME environment variable not set")

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

        # Validate datetime formats
        for field in ["start_at", "end_at"]:
            datetime_error = validate_datetime_format(body[field], field)
            if datetime_error:
                return datetime_error

        # Validate schedule times
        schedule_time_error = validate_schedule_times(body)
        if schedule_time_error:
            return schedule_time_error

        # Create schedule data
        schedule_data = create_schedule_data(body)

        # Save to database
        save_error = save_schedule_to_db(schedule_data, table_name)
        if save_error:
            return save_error

        # Return success response
        return create_success_response(schedule_data)

    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        print(f"Error creating schedule: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback

        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, "Internal server error")
