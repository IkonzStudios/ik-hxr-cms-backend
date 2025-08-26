import json
import os
import requests
from typing import Dict, Any
from utils.helpers import (
    parse_request_body,
    validate_required_fields,
    create_success_response,
    create_error_response,
    get_device_by_id_from_db,
)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to send generic commands to a device by calling external IoT API.

    Expected event structure:
    {
        "device_id": "device-uuid",
        "command": "uptime",
        "description": "To check the status of device"
    }
    """

    try:
        # Get environment variables
        devices_table_name = os.environ.get("DEVICES_TABLE_NAME")
        iot_command_api_url = os.environ.get("IOT_COMMAND_API_URL", "https://hoavw9kvxg.execute-api.us-east-2.amazonaws.com/dev/command")
        
        if not devices_table_name:
            raise ValueError("DEVICES_TABLE_NAME environment variable not set")

        # Debug: Print the event structure
        print(f"Event: {json.dumps(event)}")

        # Parse request body
        body, parse_error = parse_request_body(event)
        if parse_error:
            return parse_error

        # Validate required fields
        required_fields = ["device_id", "command"]
        validation_error = validate_required_fields(body, required_fields)
        if validation_error:
            return validation_error

        device_id = body["device_id"]
        command = body["command"]
        description = body.get("description", "")  # Optional field

        # Validate command
        if not isinstance(command, str) or not command.strip():
            return create_error_response(400, "command must be a non-empty string")

        # Validate description if provided
        if description and not isinstance(description, str):
            return create_error_response(400, "description must be a string")

        # Check if device exists in our database
        device, device_error = get_device_by_id_from_db(device_id, devices_table_name)
        if device_error:
            return device_error

        # Prepare payload for external IoT API
        iot_payload = {
            "action": "generic_command",
            "thingName": device_id,
            "payload": {
                "command": command.strip()
            }
        }

        # Add description if provided
        if description:
            iot_payload["payload"]["description"] = description.strip()

        print(f"IoT API Payload: {json.dumps(iot_payload)}")

        # Call external IoT API
        try:
            response = requests.post(
                iot_command_api_url,
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
                    "command": command,
                    "description": description,
                    "status": "command_sent",
                    "iot_response": iot_response
                })
            else:
                return create_error_response(
                    response.status_code, 
                    f"Failed to send command to device. IoT API returned: {response.text}"
                )

        except requests.exceptions.RequestException as e:
            print(f"Error calling IoT API: {str(e)}")
            return create_error_response(500, f"Failed to communicate with IoT API: {str(e)}")

    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        print(f"Error sending command to device: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, "Internal server error")
