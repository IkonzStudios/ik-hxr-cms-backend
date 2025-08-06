import json
import boto3
from datetime import datetime
from typing import Dict, Any, Tuple, Optional, List


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


def validate_required_fields(body: Dict[str, Any], required_fields: List[str]) -> Optional[Dict[str, Any]]:
    """
    Validate that all required fields are present in the request body.

    Args:
        body: Request body dictionary
        required_fields: List of required field names

    Returns:
        None if validation passes, error response dict if validation fails
    """
    for field in required_fields:
        if field not in body or body[field] is None:
            return {
                "statusCode": 400,
                "headers": get_cors_headers(),
                "body": json.dumps({"error": f'{field} is required'}),
            }
    return None


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


def create_success_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a successful response for IoT operations.

    Returns:
        Success response dictionary
    """
    return {
        "statusCode": 200,
        "headers": get_cors_headers(),
        "body": json.dumps({
            "message": "Device configuration successful",
            "data": data
        }),
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