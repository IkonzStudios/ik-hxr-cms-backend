import json
import boto3
import uuid
from datetime import datetime
from typing import Dict, Any, Tuple, Optional
from .constants import (
    REQUIRED_APPLICATION_FIELDS,
    APPLICATION_FIELD_TYPES,
    VALID_PLATFORMS,
    VALID_STATUS,
    VALID_APPLICATION_TYPES,
)


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
                "headers": get_cors_headers(),
                "body": json.dumps({"error": f'{field["name"]} is required'}),
            }
    return None


def create_application_data(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create the application data dictionary from the request body.

    Returns:
        Complete application data dictionary ready for DynamoDB
    """
    # Generate application ID and timestamps
    application_id = str(uuid.uuid4())
    current_time = datetime.now().isoformat()

    # Create application data dictionary
    application_data = {
        "id": application_id,
        "name": body["name"],
        "description": body.get("description", ""),
        "status": body.get("status", "pending"),
        "logo": body.get("logo", ""),
        "version": body["version"],
        "platform": body["platform"],
        "organization_id": body["organization_id"],
        "type": body.get("type", ""),
        "url": body.get("url", ""),
        "is_deleted": body.get("is_deleted", False),
        "created_at": current_time,
        "updated_at": current_time,
        "created_by": body.get("created_by", ""),
        "updated_by": body.get("updated_by", ""),
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

        table.put_item(
            Item=application_data, ConditionExpression="attribute_not_exists(id)"
        )
        return None

    except Exception as e:
        print(f"Error creating application: {str(e)}")
        print(f"Error type: {type(e)}")
        print(f"Error message: {str(e)}")
        return {
            "statusCode": 409,
            "headers": get_cors_headers(),
            "body": json.dumps({"error": "Application with this ID already exists"}),
        }


def create_success_response(application_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a success response with application data.

    Returns:
        Success response dictionary
    """
    return {
        "statusCode": 201,
        "headers": get_cors_headers(),
        "body": json.dumps(
            {"message": "Application created successfully", "data": application_data}
        ),
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


def get_application_by_id_from_db(
    application_id: str, table_name: str
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Get application by ID from DynamoDB.

    Returns:
        Tuple of (application_data, error_response)
        If successful: (application_dict, None)
        If error: (None, error_response_dict)
    """
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)

        response = table.get_item(Key={"id": application_id})

        if "Item" not in response:
            return None, {
                "statusCode": 404,
                "headers": get_cors_headers(),
                "body": json.dumps({"error": "Application not found"}),
            }

        return response["Item"], None

    except Exception as e:
        print(f"Error getting application: {str(e)}")
        return None, {
            "statusCode": 500,
            "headers": get_cors_headers(),
            "body": json.dumps({"error": "Internal server error"}),
        }


def get_applications_by_org_id_from_db(
    org_id: str, table_name: str
) -> Tuple[Optional[list], Optional[Dict[str, Any]]]:
    """
    Get all applications by organization ID from DynamoDB.

    Returns:
        Tuple of (applications_list, error_response)
        If successful: (applications_list, None)
        If error: (None, error_response_dict)
    """
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)

        response = table.scan(
            FilterExpression="organization_id = :org_id",
            ExpressionAttributeValues={":org_id": org_id},
        )

        return response["Items"], None

    except Exception as e:
        print(f"Error getting applications by organization ID: {str(e)}")
        return None, {
            "statusCode": 500,
            "headers": get_cors_headers(),
            "body": json.dumps({"error": "Internal server error"}),
        }


def update_application_in_db(
    application_id: str, update_data: Dict[str, Any], table_name: str
) -> Optional[Dict[str, Any]]:
    """
    Update application in DynamoDB.

    Returns:
        None if successful, error response dict if failed
    """
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)

        # Build update expression
        update_expression = "SET "
        expression_attribute_values = {}
        expression_attribute_names = {}

        for key, value in update_data.items():
            if key == "updated_at":
                update_expression += "updated_at = :updated_at, "
                expression_attribute_values[":updated_at"] = value
            else:
                # Use attribute names to handle reserved words
                attr_name = f"#{key}"
                attr_value = f":{key}"
                expression_attribute_names[attr_name] = key
                expression_attribute_values[attr_value] = value
                update_expression += f"{attr_name} = {attr_value}, "

        # Remove trailing comma and space
        update_expression = update_expression.rstrip(", ")

        # Always update the updated_at timestamp
        current_time = datetime.now().isoformat()
        update_expression += ", updated_at = :current_time"
        expression_attribute_values[":current_time"] = current_time

        table.update_item(
            Key={"id": application_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values,
            ExpressionAttributeNames=expression_attribute_names
            if expression_attribute_names
            else None,
            ConditionExpression="attribute_exists(id)",
        )

        return None

    except Exception as e:
        print(f"Error updating application: {str(e)}")
        if "ConditionalCheckFailedException" in str(e):
            return {
                "statusCode": 404,
                "headers": get_cors_headers(),
                "body": json.dumps({"error": "Application not found"}),
            }
        return {
            "statusCode": 500,
            "headers": get_cors_headers(),
            "body": json.dumps({"error": "Internal server error"}),
        }


def prepare_update_data(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepare update data from request body, filtering out invalid fields.

    Returns:
        Dictionary with valid update fields
    """
    allowed_fields = [
        "name",
        "description",
        "status",
        "logo",
        "version",
        "platform",
        "updated_by",
        "is_deleted",
        "type",
        "url",
    ]

    update_data = {}

    for field in allowed_fields:
        if field in body:
            if field == "platform":
                # Validate platform
                if body[field] in VALID_PLATFORMS:
                    update_data[field] = body[field]
                else:
                    update_data[field] = "web"  # Default to web if invalid
            elif field == "type":
                # Validate type
                if body[field] in VALID_APPLICATION_TYPES:
                    update_data[field] = body[field]
                else:
                    # Don't update if invalid type
                    continue
            else:
                update_data[field] = body[field]

    return update_data


def create_applications_list_response(applications: list) -> Dict[str, Any]:
    """
    Create a response with list of applications.

    Returns:
        Response dictionary with applications list
    """
    return {
        "statusCode": 200,
        "headers": get_cors_headers(),
        "body": json.dumps(
            {
                "message": "Applications retrieved successfully",
                "data": applications,
                "count": len(applications),
            }
        ),
    }


def create_application_response(application: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a response with single application data.

    Returns:
        Response dictionary with application data
    """
    return {
        "statusCode": 200,
        "headers": get_cors_headers(),
        "body": json.dumps(
            {"message": "Application retrieved successfully", "data": application}
        ),
    }


def validate_application_fields(body: Dict[str, Any]) -> Optional[str]:
    """
    Validate application fields for proper data types.

    Args:
        body: The request body containing application fields

    Returns:
        Error message if validation fails, None if validation passes
    """
    for field_name, field_type in APPLICATION_FIELD_TYPES.items():
        if field_name in body:
            value = body[field_name]
            if value is not None and not isinstance(value, field_type):
                try:
                    # Try to convert to the expected type
                    if field_type == str:
                        body[field_name] = str(value)
                except (ValueError, TypeError):
                    return f"Field '{field_name}' must be of type {field_type.__name__}"

    # Validate platform
    if "platform" in body and body["platform"] not in VALID_PLATFORMS:
        return f"Platform must be one of: {', '.join(VALID_PLATFORMS)}"

    # Validate status
    if "status" in body and body["status"] not in VALID_STATUS:
        return f"Status must be one of: {', '.join(VALID_STATUS)}"

    # Validate type
    if "type" in body and body["type"] and body["type"] not in VALID_APPLICATION_TYPES:
        return f"Type must be one of: {', '.join(VALID_APPLICATION_TYPES)}"

    return None
