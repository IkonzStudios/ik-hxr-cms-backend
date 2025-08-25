import json
import os
import requests
import uuid
from typing import Dict, Any
from utils.helpers import (
    parse_request_body,
    validate_required_fields,
    create_success_response,
    create_error_response,
    get_device_by_id_from_db,
)


def assign_content_to_device(device_id: str, assignment_id: str, contents: list, devices_table_name: str = None) -> Dict[str, Any]:
    """
    Utility function to assign content to a device by calling external IoT API.
    This function can be imported and used by other Lambda functions.
    
    Args:
        device_id: The device ID to assign content to
        assignment_id: Unique identifier for the assignment
        contents: List of content dictionaries with s3_bucket and s3_key
        devices_table_name: DynamoDB table name (optional, will use env var if not provided)
    
    Returns:
        Result dictionary with success/error status
    """
    try:
        # Get environment variables
        if not devices_table_name:
            devices_table_name = os.environ.get("DEVICES_TABLE_NAME")
        iot_assign_api_url = os.environ.get("IOT_ASSIGN_API_URL", "https://hoavw9kvxg.execute-api.us-east-2.amazonaws.com/dev/assign")
        
        if not devices_table_name:
            raise ValueError("DEVICES_TABLE_NAME environment variable not set")

        # Validate inputs
        if not device_id or not isinstance(device_id, str):
            return {"error": "device_id must be a non-empty string", "status_code": 400}
        
        if not assignment_id or not isinstance(assignment_id, str):
            return {"error": "assignment_id must be a non-empty string", "status_code": 400}

        # Validate contents structure
        if not isinstance(contents, list) or len(contents) == 0:
            return {"error": "contents must be a non-empty array", "status_code": 400}

        # Validate each content item
        for i, content in enumerate(contents):
            if not isinstance(content, dict):
                return {"error": f"contents[{i}] must be an object", "status_code": 400}
            
            if "s3_bucket" not in content:
                return {"error": f"contents[{i}].s3_bucket is required", "status_code": 400}
            
            if "s3_key" not in content:
                return {"error": f"contents[{i}].s3_key is required", "status_code": 400}

            if not isinstance(content["s3_bucket"], str) or not content["s3_bucket"].strip():
                return {"error": f"contents[{i}].s3_bucket must be a non-empty string", "status_code": 400}
            
            if not isinstance(content["s3_key"], str) or not content["s3_key"].strip():
                return {"error": f"contents[{i}].s3_key must be a non-empty string", "status_code": 400}

        # Check if device exists in our database
        device, device_error = get_device_by_id_from_db(device_id, devices_table_name)
        if device_error:
            return {"error": "Device not found", "status_code": 404}

        # Transform contents to match IoT API format
        iot_contents = []
        for content in contents:
            iot_contents.append({
                "s3Bucket": content["s3_bucket"],
                "s3Key": content["s3_key"]
            })

        # Prepare payload for external IoT API
        iot_payload = {
            "action": "assign_content",
            "thingName": device_id,
            "payload": {
                "assignmentId": assignment_id,
                "contents": iot_contents
            }
        }

        print(f"IoT API Payload: {json.dumps(iot_payload)}")

        # Call external IoT API
        try:
            response = requests.post(
                iot_assign_api_url,
                json=iot_payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            print(f"IoT API Response Status: {response.status_code}")
            print(f"IoT API Response: {response.text}")

            if response.status_code == 200:
                # Parse the IoT API response
                iot_response = response.json() if response.text else {}
                
                return {
                    "success": True,
                    "device_id": device_id,
                    "assignment_id": assignment_id,
                    "status": "assigned",
                    "contents_count": len(contents),
                    "iot_response": iot_response
                }
            else:
                return {
                    "error": f"Failed to assign content to device. IoT API returned: {response.text}",
                    "status_code": response.status_code
                }

        except requests.exceptions.RequestException as e:
            print(f"Error calling IoT API: {str(e)}")
            return {"error": f"Failed to communicate with IoT API: {str(e)}", "status_code": 500}

    except ValueError as e:
        return {"error": str(e), "status_code": 400}
    except Exception as e:
        print(f"Error assigning content to device: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return {"error": "Internal server error", "status_code": 500}


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler that wraps the assign_content_to_device utility function.
    This can be used if the function is deployed as a standalone Lambda.
    """
    try:
        # Debug: Print the event structure
        print(f"Event: {json.dumps(event)}")

        # Parse request body
        body, parse_error = parse_request_body(event)
        if parse_error:
            return parse_error

        # Validate required fields
        required_fields = ["device_id", "assignment_id", "contents"]
        validation_error = validate_required_fields(body, required_fields)
        if validation_error:
            return validation_error

        # Call the utility function
        result = assign_content_to_device(
            device_id=body["device_id"],
            assignment_id=body["assignment_id"],
            contents=body["contents"]
        )

        # Handle result
        if "error" in result:
            return create_error_response(result.get("status_code", 500), result["error"])
        else:
            return create_success_response(result)

    except Exception as e:
        print(f"Error in handler: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, "Internal server error")
