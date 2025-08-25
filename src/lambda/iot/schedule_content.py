import json
import os
import requests
from datetime import datetime
from typing import Dict, Any
from utils.helpers import (
    parse_request_body,
    validate_required_fields,
    create_success_response,
    create_error_response,
    get_device_by_id_from_db,
)


def validate_iso_datetime(date_string: str) -> bool:
    """
    Validate if the date string is in ISO 8601 format.
    
    Args:
        date_string: The date string to validate
        
    Returns:
        True if valid, False otherwise
    """
    try:
        datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        return True
    except ValueError:
        return False


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to schedule content on a device by calling external IoT API.

    Expected event structure:
    {
        "device_id": "device-uuid",
        "schedule_id": "schedule-123",
        "schedule_type": "multimedia",
        "schedule_start_time": "2025-08-22T09:35:00Z",
        "schedule_end_time": "2025-08-22T09:55:00Z",
        "content_payload": {
            "contents": [
                { "s3_key": "hxr/vid1_new.mp4" },
                { "s3_key": "hxr/vid3_new.mp4" }
            ]
        }
    }
    """

    try:
        # Get environment variables
        devices_table_name = os.environ.get("DEVICES_TABLE_NAME")
        iot_schedule_api_url = os.environ.get("IOT_SCHEDULE_API_URL", "https://hoavw9kvxg.execute-api.us-east-2.amazonaws.com/dev/schedule")
        
        if not devices_table_name:
            raise ValueError("DEVICES_TABLE_NAME environment variable not set")

        # Debug: Print the event structure
        print(f"Event: {json.dumps(event)}")

        # Parse request body
        body, parse_error = parse_request_body(event)
        if parse_error:
            return parse_error

        # Validate required fields
        required_fields = ["device_id", "schedule_id", "schedule_type", "schedule_start_time", "schedule_end_time", "content_payload"]
        validation_error = validate_required_fields(body, required_fields)
        if validation_error:
            return validation_error

        device_id = body["device_id"]
        schedule_id = body["schedule_id"]
        schedule_type = body["schedule_type"]
        schedule_start_time = body["schedule_start_time"]
        schedule_end_time = body["schedule_end_time"]
        content_payload = body["content_payload"]

        # Validate schedule_type
        if not isinstance(schedule_type, str) or not schedule_type.strip():
            return create_error_response(400, "schedule_type must be a non-empty string")

        # Validate datetime formats
        if not validate_iso_datetime(schedule_start_time):
            return create_error_response(400, "schedule_start_time must be in ISO 8601 format (e.g., 2025-08-22T09:35:00Z)")
        
        if not validate_iso_datetime(schedule_end_time):
            return create_error_response(400, "schedule_end_time must be in ISO 8601 format (e.g., 2025-08-22T09:55:00Z)")

        # Validate that start time is before end time
        try:
            start_dt = datetime.fromisoformat(schedule_start_time.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(schedule_end_time.replace('Z', '+00:00'))
            
            if start_dt >= end_dt:
                return create_error_response(400, "schedule_start_time must be before schedule_end_time")
        except ValueError as e:
            return create_error_response(400, f"Invalid datetime format: {str(e)}")

        # Validate content_payload structure
        if not isinstance(content_payload, dict):
            return create_error_response(400, "content_payload must be an object")
        
        if "contents" not in content_payload:
            return create_error_response(400, "content_payload.contents is required")
        
        contents = content_payload["contents"]
        if not isinstance(contents, list) or len(contents) == 0:
            return create_error_response(400, "content_payload.contents must be a non-empty array")

        # Validate each content item
        for i, content in enumerate(contents):
            if not isinstance(content, dict):
                return create_error_response(400, f"content_payload.contents[{i}] must be an object")
            
            if "s3_key" not in content:
                return create_error_response(400, f"content_payload.contents[{i}].s3_key is required")
            
            if not isinstance(content["s3_key"], str) or not content["s3_key"].strip():
                return create_error_response(400, f"content_payload.contents[{i}].s3_key must be a non-empty string")

        # Check if device exists in our database
        device, device_error = get_device_by_id_from_db(device_id, devices_table_name)
        if device_error:
            return device_error

        # Prepare payload for external IoT API
        iot_payload = {
            "action": "schedule_content",
            "thingName": device_id,
            "payload": {
                "scheduleId": schedule_id,
                "scheduleType": schedule_type,
                "scheduleStartTime": schedule_start_time,
                "scheduleEndTime": schedule_end_time,
                "contentPayload": content_payload
            }
        }

        print(f"IoT API Payload: {json.dumps(iot_payload)}")

        # Call external IoT API
        try:
            response = requests.post(
                iot_schedule_api_url,
                json=iot_payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            print(f"IoT API Response Status: {response.status_code}")
            print(f"IoT API Response: {response.text}")

            if response.status_code == 200:
                # Parse the IoT API response
                iot_response = response.json() if response.text else {}
                
                return create_success_response({
                    "device_id": device_id,
                    "schedule_id": schedule_id,
                    "schedule_type": schedule_type,
                    "schedule_start_time": schedule_start_time,
                    "schedule_end_time": schedule_end_time,
                    "status": "scheduled",
                    "contents_count": len(contents),
                    "iot_response": iot_response
                })
            else:
                return create_error_response(
                    response.status_code, 
                    f"Failed to schedule content on device. IoT API returned: {response.text}"
                )

        except requests.exceptions.RequestException as e:
            print(f"Error calling IoT API: {str(e)}")
            return create_error_response(500, f"Failed to communicate with IoT API: {str(e)}")

    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        print(f"Error scheduling content on device: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, "Internal server error")
