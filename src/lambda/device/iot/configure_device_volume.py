import json
import os
import requests
import traceback
from typing import Dict, Any

from utils.helpers import (
    parse_request_body,
    get_device_by_id_from_db,
    create_device_response,
    create_error_response,
)
from utils.rbac import check_edit_permission_with_org
from utils.constants import HTTP_STATUS_CODES, DEVICE_ERROR_MESSAGES, DEVICE_SUCCESS_MESSAGES


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to configure device volume by calling external IoT API.

    Expected event structure:
    {
        "pathParameters": {
            "id": "device-uuid"
        },
        "body": {
            "volume": 80
        }
    }
    """

    try:
        # Get environment variables
        devices_table_name = os.environ.get("DEVICES_TABLE_NAME")
        iot_api_url = os.environ.get("IOT_API_URL")
        
        if not devices_table_name:
            return create_error_response(500, DEVICE_ERROR_MESSAGES["MISSING_ENVIRONMENT_VAR"])

        # Debug: Print the event structure
        print(f"Event: {json.dumps(event)}")

        # Extract device ID from path parameters
        path_parameters = event.get("pathParameters", {})
        device_id = path_parameters.get("id") if path_parameters else None

        if not device_id:
            return create_error_response(400, DEVICE_ERROR_MESSAGES["DEVICE_ID_REQUIRED"])

        # First get the existing device to check its organization_id for RBAC
        existing_device, get_error = get_device_by_id_from_db(device_id, devices_table_name)
        if get_error:
            return get_error

        # RBAC: Check if user has permission to edit devices in this organization
        rbac_error, user_info = check_edit_permission_with_org(event, "device", existing_device["organization_id"])
        if rbac_error:
            return rbac_error

        # Log user action for audit
        print(f"User {user_info['user_id']} ({user_info['role']}) configuring volume for device {device_id}")

        # Parse request body
        body, parse_error = parse_request_body(event)
        if parse_error:
            return parse_error

        # Check if body has volume
        if not body:
            return create_error_response(400, DEVICE_ERROR_MESSAGES["EMPTY_REQUEST_BODY"])

        volume = body.get("volume")
        if volume is None:
            return create_error_response(400, "Volume value is required")

        # Validate volume range (0-100)
        if not isinstance(volume, (int, float)) or volume < 0 or volume > 100:
            return create_error_response(400, DEVICE_ERROR_MESSAGES["VOLUME_RANGE_ERROR"])

        # Prepare payload for external IoT API
        iot_payload = {
            "action": "config",
            "thingName": device_id,
            "desiredState": {
                "volume": volume
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
                
                # Create volume configuration result
                volume_config_result = {
                    "success": True,
                    "message": DEVICE_SUCCESS_MESSAGES["VOLUME_CONFIGURED"],
                    "volume": volume,
                    "iot_response": iot_response
                }
                
                print(f"Volume configuration successful for device {device_id}")
                return create_device_response(existing_device, {"volume_configuration": volume_config_result})
            else:
                error_msg = f"{DEVICE_ERROR_MESSAGES['IOT_CONFIG_FAILED']}: IoT API returned status {response.status_code}: {response.text}"
                return create_error_response(502, error_msg)

        except requests.exceptions.RequestException as e:
            print(f"Error calling IoT API: {str(e)}")
            return create_error_response(502, f"{DEVICE_ERROR_MESSAGES['IOT_API_ERROR']}: {str(e)}")

    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        print(f"Error configuring device volume: {str(e)}")
        print(f"Error type: {type(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, HTTP_STATUS_CODES[500])
