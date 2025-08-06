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
    Lambda function to configure device brightness by calling external IoT API.

    Expected event structure:
    {
        "device_id": "device-uuid",
        "brightness": 90
    }
    """

    try:
        # Get environment variables
        devices_table_name = os.environ.get("DEVICES_TABLE_NAME")
        iot_api_url = os.environ.get("IOT_API_URL", "https://hoavw9kvxg.execute-api.us-east-2.amazonaws.com/dev/config")
        
        if not devices_table_name:
            raise ValueError("DEVICES_TABLE_NAME environment variable not set")

        # Debug: Print the event structure
        print(f"Event: {json.dumps(event)}")

        # Parse request body
        body, parse_error = parse_request_body(event)
        if parse_error:
            return parse_error

        # Validate required fields
        required_fields = ["device_id", "brightness"]
        validation_error = validate_required_fields(body, required_fields)
        if validation_error:
            return validation_error

        device_id = body["device_id"]
        brightness = body["brightness"]

        # Validate brightness range (0-100)
        if not isinstance(brightness, (int, float)) or brightness < 0 or brightness > 100:
            return create_error_response(400, "Brightness must be a number between 0 and 100")

        # Check if device exists in our database
        device, device_error = get_device_by_id_from_db(device_id, devices_table_name)
        if device_error:
            return device_error

        # Prepare payload for external IoT API
        iot_payload = {
            "action": "config",
            "thingName": device_id,
            "desiredState": {
                "brightness": brightness
            }
        }

        # Call external IoT API
        try:
            response = requests.post(
                iot_api_url,
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
                    "status": "configured",
                    "brightness": brightness,
                })
            else:
                return create_error_response(
                    response.status_code, 
                    f"Failed to configure device brightness. IoT API returned: {response.text}"
                )

        except requests.exceptions.RequestException as e:
            print(f"Error calling IoT API: {str(e)}")
            return create_error_response(500, f"Failed to communicate with IoT API: {str(e)}")

    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        print(f"Error configuring device brightness: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, "Internal server error") 