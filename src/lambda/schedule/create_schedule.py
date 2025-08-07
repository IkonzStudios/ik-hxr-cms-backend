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
    schedule_content_on_iot_devices,
)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to create a new schedule in DynamoDB.

    Expected event structure:
    {
        "title": "My Schedule Title",
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
        # Get environment variables
        schedules_table_name = os.environ.get("SCHEDULES_TABLE_NAME")
        playlists_table_name = os.environ.get("PLAYLISTS_TABLE_NAME")
        contents_table_name = os.environ.get("CONTENTS_TABLE_NAME")
        iot_schedule_api_url = os.environ.get("IOT_SCHEDULE_API_URL")
        default_s3_bucket = os.environ.get("CONTENT_BUCKET_NAME")
        
        if not schedules_table_name:
            raise ValueError("SCHEDULES_TABLE_NAME environment variable not set")
        if not playlists_table_name:
            raise ValueError("PLAYLISTS_TABLE_NAME environment variable not set")
        if not contents_table_name:
            raise ValueError("CONTENTS_TABLE_NAME environment variable not set")
        if not iot_schedule_api_url:
            raise ValueError("IOT_SCHEDULE_API_URL environment variable not set")
        if not default_s3_bucket:
            raise ValueError("CONTENT_BUCKET_NAME environment variable not set")

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
        save_error = save_schedule_to_db(schedule_data, schedules_table_name)
        if save_error:
            return save_error

        # Schedule content on IoT devices after successful DB save
        iot_success, iot_errors, iot_responses = schedule_content_on_iot_devices(
            schedule_data=schedule_data,
            playlists_table_name=playlists_table_name,
            contents_table_name=contents_table_name,
            iot_api_url=iot_schedule_api_url,
            default_s3_bucket=default_s3_bucket
        )
        
        # Create enhanced response with IoT scheduling results
        response_data = {
            "schedule": schedule_data,
            "iot_scheduling": {
                "success": iot_success,
                "errors": iot_errors,
                "device_responses": iot_responses
            }
        }
        
        if iot_success:
            return {
                "statusCode": 201,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token,X-Requested-With,Origin,Accept,Cache-Control,Pragma,If-Modified-Since,X-Forwarded-For,X-Forwarded-Proto,X-Forwarded-Port",
                    "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS,PATCH,HEAD",
                    "Access-Control-Max-Age": "86400",
                },
                "body": json.dumps({
                    "message": "Schedule created and IoT devices scheduled successfully",
                    "data": response_data
                }),
            }
        else:
            # Schedule was created but IoT scheduling failed
            return {
                "statusCode": 207,  # Multi-status: partial success
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token,X-Requested-With,Origin,Accept,Cache-Control,Pragma,If-Modified-Since,X-Forwarded-For,X-Forwarded-Proto,X-Forwarded-Port",
                    "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS,PATCH,HEAD",
                    "Access-Control-Max-Age": "86400",
                },
                "body": json.dumps({
                    "message": "Schedule created successfully but IoT scheduling failed",
                    "data": response_data,
                    "warning": "Some or all IoT devices could not be scheduled"
                }),
            }

    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        print(f"Error creating schedule: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback

        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, "Internal server error")
