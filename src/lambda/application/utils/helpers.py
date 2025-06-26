import json
import os
import boto3
from decimal import Decimal
from utils.constants import REQUIRED_APPLICATION_FIELDS
from typing import Dict, Any, Tuple, Optional
from datetime import datetime
import uuid

dynamodb = boto3.resource("dynamodb")
APPLICATIONS_TABLE = os.environ.get("APPLICATIONS_TABLE_NAME")
table = dynamodb.Table(APPLICATIONS_TABLE)

import json
from typing import Dict, Any, Optional, Tuple


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
                    "body": json.dumps({"error": "Invalid JSON in request body"}),
                }
        elif isinstance(event["body"], dict):
            body = event["body"]
        else:
            print(f"Unexpected body type: {type(event['body'])}")
            return None, {
                "statusCode": 400,
                "body": json.dumps({"error": "Invalid request body format"}),
            }

    # Ensure body is a dictionary
    if not isinstance(body, dict):
        print(f"Body is not a dictionary: {type(body)}")
        return None, {
            "statusCode": 400,
            "body": json.dumps({"error": "Request body must be a JSON object"}),
        }

    return body, None

def validate_required_fields(body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Validate that all required fields are present in the request body.

    Returns:
        None if validation passes, error response dict if validation fails
    """
    for field in REQUIRED_APPLICATION_FIELDS:
        if not body.get(field["column_name"]):
            return {
                "statusCode": 400,
                "body": json.dumps({"error": f'{field["name"]} is required'}),
            }
    return None


def create_application_data(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create the application data dictionary from the request body.

    Returns:
        Complete application data dictionary ready for DynamoDB
    """
    application_id = str(uuid.uuid4())
    current_time = datetime.now().isoformat()

    application_data = {
        "id": application_id,
        "name": body["name"],
        "author": body.get("author"),
        "status": body.get("status", "active"),
        "created_at": current_time,
        "updated_at": current_time,
    }

    return application_data


def save_application_to_db(
    application_data: Dict[str, Any], table_name: str
) -> Optional[Dict[str, Any]]:
    """
    Save application data to DynamoDB.

    Returns:
        None if successful, error response dict if failed
    """
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)

        table.put_item(Item=application_data, ConditionExpression="attribute_not_exists(id)")
        return None

    except Exception as e:
        print(f"Error creating application: {str(e)}")
        print(f"Error type: {type(e)}")
        print(f"Error message: {str(e)}")
        return {
            "statusCode": 409,
            "body": json.dumps({"error": "Application with this ID already exists"}),
        }



def format_response_application(application_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format application data for JSON response by converting Decimal to float.

    Returns:
        Application data with Decimal values converted to float
    """
    response_application = application_data.copy()

    if response_application.get("storage_left") is not None:
        response_application["storage_left"] = float(response_application["storage_left"])
    if response_application.get("storage_consumed") is not None:
        response_application["storage_consumed"] = float(response_application["storage_consumed"])

    return response_application


def create_success_response(application_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a successful response for application creation.

    Returns:
        Success response dictionary
    """
    response_application = format_response_application(application_data)

    return {
        "statusCode": 201,
        "body": json.dumps(
            {
                "message": "Application created successfully",
                "application_id": application_data["id"],
                "application": response_application,
            }
            
        ),
    }

def create_error_response(status_code: int, error_message: str) -> Dict[str, Any]:
    """
    Create an error response.

    Returns:
        Error response dictionary
    """
    return {"statusCode": status_code, "body": json.dumps({"error": error_message})}

# def create_application_response(application):
#     return {
#         "id": application["id"],
#         "name": application["name"],
#         "author": application["author"],
#         "status": application["status"],
#         "created_at": application["created_at"],
#         "updated_at": application["updated_at"],
#     }

def get_application_by_id_from_db(
    app_id: str, table_name: str
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Get a App by ID from DynamoDB.

    Returns:
        Tuple of (device_data, error_response)
        If successful: (device_dict, None)
        If error: (None, error_response_dict)
    """
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)

        response = table.get_item(Key={"id": app_id})

        if "Item" not in response:
            return None, {
                "statusCode": 404,
                "body": json.dumps({"error": "Application not found"}),
            }

        return response["Item"], None

    except Exception as e:
        print(f"Error getting application: {str(e)}")
        return None, {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"}),
        }
def create_applications_list_response(applications: list) -> Dict[str, Any]:
    """
    Create a successful response for application list.

    Returns:
        Success response dictionary with application list
    """
    # Format application for response
    formatted_applications = []
    for application in applications:
        formatted_item = format_response_application(application)
        formatted_applications.append(formatted_item)

    return {
        "statusCode": 200,
        "body": json.dumps(
            {"devices": formatted_applications, "count": len(formatted_applications)}
        ),
    }

def create_application_response(application: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a successful response for single application.

    Returns:
        Success response dictionary with application data
    """
    formatted_application = format_response_application(application)
    return {"statusCode": 200, "body": json.dumps({"application": formatted_application})}