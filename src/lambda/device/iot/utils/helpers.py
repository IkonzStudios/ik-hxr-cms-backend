import json
import os
import boto3
from datetime import datetime
from typing import Dict, Any, Tuple, Optional, List


def get_iot_url_for_device(
    device: Optional[Dict[str, Any]],
    url_env_key: str,
    url_old_env_key: str,
) -> str:
    """
    Return the IoT API URL to use based on the device's region.
    If device has region "us-east-2", use the _OLD URL (Ohio); otherwise use the default URL.
    """
    if device and device.get("region") == "us-east-2":
        return os.environ.get(url_old_env_key) or os.environ.get(url_env_key) or ""
    return os.environ.get(url_env_key) or ""


def get_cors_headers() -> Dict[str, str]:
    """
    Get standard CORS headers for all responses.

    Returns:
        Dictionary with CORS headers
    """
    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token,X-Requested-With,Origin,Accept,Cache-Control,Pragma,If-Modified-Since,X-Forwarded-For,X-Forwarded-Proto,X-Forwarded-Port",
        "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS,PATCH,HEAD",
        "Access-Control-Max-Age": "86400",
    }


def parse_request_body(
    event: Dict[str, Any]
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Parse the request body from the event.

    Returns:
        Tuple of (parsed_body, error_response)
        If successful: (body_dict, None)
        If error: (None, error_response_dict)
    """
    body = None

    if "body" in event:
        if isinstance(event["body"], str):
            try:
                body = json.loads(event["body"])
            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e}")
                return None, {
                    "statusCode": 400,
                    "headers": get_cors_headers(),
                    "body": json.dumps({"error": "Invalid JSON in request body"}),
                }
        elif isinstance(event["body"], dict):
            body = event["body"]
        else:
            print(f"Unexpected body type: {type(event['body'])}")
            return None, {
                "statusCode": 400,
                "headers": get_cors_headers(),
                "body": json.dumps({"error": "Invalid request body format"}),
            }

    # Ensure body is a dictionary
    if not isinstance(body, dict):
        print(f"Body is not a dictionary: {type(body)}")
        return None, {
            "statusCode": 400,
            "headers": get_cors_headers(),
            "body": json.dumps({"error": "Request body must be a JSON object"}),
        }

    return body, None


def get_device_by_id_from_db(
    device_id: str, table_name: str
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Get a device by ID from DynamoDB.

    Returns:
        Tuple of (device_data, error_response)
        If successful: (device_dict, None)
        If error: (None, error_response_dict)
    """
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)

        response = table.get_item(Key={"id": device_id})

        if "Item" not in response:
            return None, {
                "statusCode": 404,
                "headers": get_cors_headers(),
                "body": json.dumps({"error": "Device not found"}),
            }

        return response["Item"], None

    except Exception as e:
        print(f"Error getting device: {str(e)}")
        return None, {
            "statusCode": 500,
            "headers": get_cors_headers(),
            "body": json.dumps({"error": "Internal server error"}),
        }


def create_error_response(status_code: int, error_message: str) -> Dict[str, Any]:
    """
    Create an error response.

    Returns:
        Error response dictionary
    """
    return {
        "statusCode": status_code,
        "headers": get_cors_headers(),
        "body": json.dumps({"error": error_message}),
    }


def create_device_response(device: Dict[str, Any], iot_assignment_result: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Create a successful response for single device.

    Args:
        device: Device data dictionary
        iot_assignment_result: Optional IoT assignment result for device updates

    Returns:
        Success response dictionary with device data and optional IoT results
    """
    formatted_device = format_response_device(device)
    
    # Prepare response body
    response_body = {"device": formatted_device}
    
    # Add IoT assignment result if provided
    if iot_assignment_result:
        response_body["iot_content_assignment"] = iot_assignment_result
    
    # Determine status code and message based on IoT result
    if iot_assignment_result and not iot_assignment_result.get("success", True):
        # Device update succeeded but IoT assignment failed
        status_code = 207  # Multi-status: partial success
        response_body["message"] = "Device updated successfully but IoT content assignment failed"
        response_body["warning"] = "Content assignment to IoT device failed"
    else:
        # Normal success response
        status_code = 200
        if iot_assignment_result and iot_assignment_result.get("success"):
            response_body["message"] = "Device updated successfully with IoT content assignment"
        # Note: No message for regular device operations to maintain backward compatibility

    return {
        "statusCode": status_code,
        "headers": get_cors_headers(),
        "body": json.dumps(response_body),
    }

def format_response_device(device_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format device data for JSON response by converting Decimal to float.

    Returns:
        Device data with Decimal values converted to float
    """
    response_device = device_data.copy()

    if response_device.get("storage_left") is not None:
        response_device["storage_left"] = float(response_device["storage_left"])
    if response_device.get("storage_consumed") is not None:
        response_device["storage_consumed"] = float(response_device["storage_consumed"])

    if response_device.get("cpu_usage") is not None:
        response_device["cpu_usage"] = float(response_device["cpu_usage"])
    if response_device.get("memory_usage") is not None:
        response_device["memory_usage"] = float(response_device["memory_usage"])
    
    if response_device.get("schedules") is not None and isinstance(response_device.get("schedules"), str):
        response_device["schedules"] = json.loads(response_device["schedules"])

    return response_device