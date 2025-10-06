import json
import boto3
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Tuple, Optional
from .constants import REQUIRED_PLAYBACK_FIELDS, VALID_STATUS_VALUES


def convert_decimals_to_numbers(obj):
    """
    Recursively convert Decimal objects to float/int for JSON serialization.
    
    Args:
        obj: Object that may contain Decimal values
        
    Returns:
        Object with Decimal values converted to numbers
    """
    if isinstance(obj, Decimal):
        # Convert Decimal to float, preserving precision
        return float(obj)
    elif isinstance(obj, dict):
        return {key: convert_decimals_to_numbers(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_decimals_to_numbers(item) for item in obj]
    else:
        return obj


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
    for field in REQUIRED_PLAYBACK_FIELDS:
        if not body.get(field["column_name"]):
            return {
                "statusCode": 400,
                "headers": get_cors_headers(),
                "body": json.dumps({"error": f'{field["name"]} is required'}),
            }
    return None


def validate_datetime_format(
    datetime_str: str, field_name: str
) -> Optional[Dict[str, Any]]:
    """
    Validate datetime format (ISO 8601).

    Returns:
        None if valid, error response dict if invalid
    """
    try:
        datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
        return None
    except ValueError:
        return {
            "statusCode": 400,
            "headers": get_cors_headers(),
            "body": json.dumps(
                {
                    "error": f"{field_name} must be in ISO 8601 format (e.g., '2024-01-15T10:30:00Z')"
                }
            ),
        }


def validate_playback_times(body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Validate that start_at is before end_at.

    Returns:
        None if valid, error response dict if invalid
    """
    try:
        start_at = datetime.fromisoformat(body["start_at"].replace("Z", "+00:00"))
        end_at = datetime.fromisoformat(body["end_at"].replace("Z", "+00:00"))

        if start_at >= end_at:
            return {
                "statusCode": 400,
                "headers": get_cors_headers(),
                "body": json.dumps({"error": "start_at must be before end_at"}),
            }
        return None
    except ValueError:
        return {
            "statusCode": 400,
            "headers": get_cors_headers(),
            "body": json.dumps({"error": "Invalid datetime format"}),
        }


def validate_status(status: str) -> Optional[Dict[str, Any]]:
    """
    Validate that status is one of the valid values.

    Returns:
        None if valid, error response dict if invalid
    """
    if status and status not in VALID_STATUS_VALUES:
        return {
            "statusCode": 400,
            "headers": get_cors_headers(),
            "body": json.dumps(
                {
                    "error": f"Status must be one of: {', '.join(VALID_STATUS_VALUES)}"
                }
            ),
        }
    return None


def create_playback_data(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create the playback data dictionary from the request body.

    Returns:
        Complete playback data dictionary ready for DynamoDB
    """
    # Generate playback ID and timestamps
    playback_id = str(uuid.uuid4())
    current_time = datetime.now().isoformat()

    # Create playback data dictionary
    playback_data = {
        "id": playback_id,
        "schedule_id": body["schedule_id"],
        "job_id": body["job_id"],
        "content_id": body["content_id"],
        "duration": body["duration"],
        "start_at": body["start_at"],
        "end_at": body["end_at"],
        "status": body.get("status", "created"),
        "times_played": body.get("times_played", 0),
        "organization_id": body.get("organization_id", ""),
        "created_at": current_time,
        "updated_at": current_time,
        "created_by": body.get("created_by", ""),
        "updated_by": body.get("updated_by", ""),
    }

    return playback_data


def save_playback_to_db(
    playback_data: Dict[str, Any], table_name: str
) -> Optional[Dict[str, Any]]:
    """
    Save playback data to DynamoDB.

    Returns:
        None if successful, error response dict if failed
    """
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)

        table.put_item(
            Item=playback_data, ConditionExpression="attribute_not_exists(id)"
        )
        return None

    except Exception as e:
        print(f"Error creating playback: {str(e)}")
        print(f"Error type: {type(e)}")
        print(f"Error message: {str(e)}")
        return {
            "statusCode": 409,
            "headers": get_cors_headers(),
            "body": json.dumps({"error": "Playback with this ID already exists"}),
        }


def create_success_response(playback_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a success response with playback data.

    Returns:
        Success response dictionary
    """
    # Convert Decimal objects to numbers for JSON serialization
    converted_playback_data = convert_decimals_to_numbers(playback_data)
    
    return {
        "statusCode": 201,
        "headers": get_cors_headers(),
        "body": json.dumps(
            {"message": "Playback created successfully", "data": converted_playback_data}
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


def get_playback_by_id_from_db(
    playback_id: str, table_name: str
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Get playback by ID from DynamoDB.

    Returns:
        Tuple of (playback_data, error_response)
        If successful: (playback_dict, None)
        If error: (None, error_response_dict)
    """
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)

        response = table.get_item(Key={"id": playback_id})

        if "Item" not in response:
            return None, {
                "statusCode": 404,
                "headers": get_cors_headers(),
                "body": json.dumps({"error": "Playback not found"}),
            }

        return response["Item"], None

    except Exception as e:
        print(f"Error getting playback: {str(e)}")
        return None, {
            "statusCode": 500,
            "headers": get_cors_headers(),
            "body": json.dumps({"error": "Internal server error"}),
        }


def get_playbacks_by_org_id_from_db(
    org_id: str, table_name: str, contents_table_name: str, schedules_table_name: str
) -> Tuple[Optional[list], Optional[Dict[str, Any]]]:
    """
    Get all playbacks by organization ID from DynamoDB.

    Returns:
        Tuple of (playbacks_list, error_response)
        If successful: (playbacks_list, None)
        If error: (None, error_response_dict)
    """
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)

        response = table.scan(
            FilterExpression="organization_id = :org_id",
            ExpressionAttributeValues={":org_id": org_id},
        )

        playbacks = response.get("Items", [])
        for playback in playbacks:
            print(f"Playback: {playback}")
            content_id = playback.get("content_id")
            content_data, content_error = get_content_by_id_from_db(content_id, contents_table_name)
            if content_error:
                return None, content_error
            playback["content"] = content_data
            schedule_id = playback.get("schedule_id")
            schedule_data = None
            if schedule_id:
                schedule_data, schedule_error = get_schedule_by_id_from_db(schedule_id, schedules_table_name)
                if schedule_error:
                    return None, schedule_error
            playback["schedule"] = schedule_data

        return playbacks, None

    except Exception as e:
        print(f"Error getting playbacks by organization ID: {str(e)}")
        return None, {
            "statusCode": 500,
            "headers": get_cors_headers(),
            "body": json.dumps({"error": "Internal server error"}),
        }


def update_playback_in_db(
    playback_id: str, update_data: Dict[str, Any], table_name: str
) -> Optional[Dict[str, Any]]:
    """
    Update playback in DynamoDB.

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
            Key={"id": playback_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values,
            ExpressionAttributeNames=expression_attribute_names
            if expression_attribute_names
            else None,
            ConditionExpression="attribute_exists(id)",
        )

        return None

    except Exception as e:
        print(f"Error updating playback: {str(e)}")
        if "ConditionalCheckFailedException" in str(e):
            return {
                "statusCode": 404,
                "headers": get_cors_headers(),
                "body": json.dumps({"error": "Playback not found"}),
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
        "schedule_id",
        "job_id",
        "content_id",
        "duration",
        "start_at",
        "end_at",
        "status",
        "times_played",
        "updated_by",
    ]

    update_data = {}

    for field in allowed_fields:
        if field in body:
            update_data[field] = body[field]

    return update_data


def create_playbacks_list_response(playbacks: list) -> Dict[str, Any]:
    """
    Create a response with list of playbacks.

    Returns:
        Response dictionary with playbacks list
    """
    # Convert Decimal objects to numbers for JSON serialization
    converted_playbacks = convert_decimals_to_numbers(playbacks)
    
    return {
        "statusCode": 200,
        "headers": get_cors_headers(),
        "body": json.dumps(
            {
                "message": "Playbacks retrieved successfully",
                "data": converted_playbacks,
                "count": len(converted_playbacks),
            }
        ),
    }


def create_playback_response(playback: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a response with single playback data.

    Returns:
        Response dictionary with playback data
    """
    # Convert Decimal objects to numbers for JSON serialization
    converted_playback = convert_decimals_to_numbers(playback)
    
    return {
        "statusCode": 200,
        "headers": get_cors_headers(),
        "body": json.dumps(
            {"message": "Playback retrieved successfully", "data": converted_playback}
        ),
    }

def get_content_by_id_from_db(
    content_id: str, table_name: str
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Get content by ID from DynamoDB.
    """
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)
        response = table.get_item(Key={"id": content_id})
        return response["Item"], None
    except Exception as e:
        print(f"Error getting content: {str(e)}")
        return None, {
            "statusCode": 500,
            "headers": get_cors_headers(),
            "body": json.dumps({"error": "Internal server error"}),
        }

def get_schedule_by_id_from_db(
    schedule_id: str, table_name: str
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Get schedule by ID from DynamoDB.
    """
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)
        response = table.get_item(Key={"id": schedule_id})
        return response["Item"], None
    except Exception as e:
        print(f"Error getting schedule: {str(e)}")
        return None, {
            "statusCode": 500,
            "headers": get_cors_headers(),
            "body": json.dumps({"error": "Internal server error"}),
        }
