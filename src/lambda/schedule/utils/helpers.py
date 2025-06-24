import json
import boto3
import uuid
from datetime import datetime
from typing import Dict, Any, Tuple, Optional
from .constants import REQUIRED_SCHEDULE_FIELDS


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
    for field in REQUIRED_SCHEDULE_FIELDS:
        if not body.get(field["column_name"]):
            return {
                "statusCode": 400,
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
            "body": json.dumps(
                {
                    "error": f"{field_name} must be in ISO 8601 format (e.g., '2024-01-15T10:30:00Z')"
                }
            ),
        }


def validate_schedule_times(body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
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
                "body": json.dumps({"error": "start_at must be before end_at"}),
            }
        return None
    except ValueError:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Invalid datetime format"}),
        }


def parse_array_fields(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse stringified array fields (assigned_to, contents, playlists) from the body.

    Returns:
        Dictionary with parsed array values
    """
    result = {}

    for field_name in ["assigned_to", "contents", "playlists"]:
        field_value = body.get(field_name)
        if isinstance(field_value, str):
            try:
                result[field_name] = json.loads(field_value)
            except json.JSONDecodeError:
                result[field_name] = []
        elif field_value is None:
            result[field_name] = []
        else:
            result[field_name] = field_value

    return result


def create_schedule_data(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create the schedule data dictionary from the request body.

    Returns:
        Complete schedule data dictionary ready for DynamoDB
    """
    # Parse array fields
    arrays = parse_array_fields(body)

    # Generate schedule ID and timestamps
    schedule_id = str(uuid.uuid4())
    current_time = datetime.now().isoformat()

    # Create schedule data dictionary
    schedule_data = {
        "id": schedule_id,
        "start_at": body["start_at"],
        "end_at": body["end_at"],
        "loop": body.get("loop", False),
        "is_active": body.get("is_active", True),
        "assigned_to": arrays["assigned_to"],
        "contents": arrays["contents"],
        "playlists": arrays["playlists"],
        "organization_id": body["organization_id"],
        "created_at": current_time,
        "updated_at": current_time,
        "created_by": body.get("created_by", ""),
        "updated_by": body.get("updated_by", ""),
    }

    return schedule_data


def save_schedule_to_db(
    schedule_data: Dict[str, Any], table_name: str
) -> Optional[Dict[str, Any]]:
    """
    Save schedule data to DynamoDB.

    Returns:
        None if successful, error response dict if failed
    """
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)

        table.put_item(
            Item=schedule_data, ConditionExpression="attribute_not_exists(id)"
        )
        return None

    except Exception as e:
        print(f"Error creating schedule: {str(e)}")
        print(f"Error type: {type(e)}")
        print(f"Error message: {str(e)}")
        return {
            "statusCode": 409,
            "body": json.dumps({"error": "Schedule with this ID already exists"}),
        }


def create_success_response(schedule_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a success response with schedule data.

    Returns:
        Success response dictionary
    """
    return {
        "statusCode": 201,
        "body": json.dumps(
            {"message": "Schedule created successfully", "data": schedule_data}
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
        "body": json.dumps({"error": error_message}),
    }


def get_schedule_by_id_from_db(
    schedule_id: str, table_name: str
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Get schedule by ID from DynamoDB.

    Returns:
        Tuple of (schedule_data, error_response)
        If successful: (schedule_dict, None)
        If error: (None, error_response_dict)
    """
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)

        response = table.get_item(Key={"id": schedule_id})

        if "Item" not in response:
            return None, {
                "statusCode": 404,
                "body": json.dumps({"error": "Schedule not found"}),
            }

        return response["Item"], None

    except Exception as e:
        print(f"Error getting schedule: {str(e)}")
        return None, {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"}),
        }


def get_schedules_by_org_id_from_db(
    org_id: str, table_name: str
) -> Tuple[Optional[list], Optional[Dict[str, Any]]]:
    """
    Get all schedules by organization ID from DynamoDB.

    Returns:
        Tuple of (schedules_list, error_response)
        If successful: (schedules_list, None)
        If error: (None, error_response_dict)
    """
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)

        response = table.scan(
            FilterExpression="organization_id = :org_id",
            ExpressionAttributeValues={":org_id": org_id},
        )

        return response.get("Items", []), None

    except Exception as e:
        print(f"Error getting schedules by organization ID: {str(e)}")
        return None, {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"}),
        }


def update_schedule_in_db(
    schedule_id: str, update_data: Dict[str, Any], table_name: str
) -> Optional[Dict[str, Any]]:
    """
    Update schedule in DynamoDB.

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
            Key={"id": schedule_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values,
            ExpressionAttributeNames=expression_attribute_names
            if expression_attribute_names
            else None,
            ConditionExpression="attribute_exists(id)",
        )

        return None

    except Exception as e:
        print(f"Error updating schedule: {str(e)}")
        if "ConditionalCheckFailedException" in str(e):
            return {
                "statusCode": 404,
                "body": json.dumps({"error": "Schedule not found"}),
            }
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"}),
        }


def prepare_update_data(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepare update data from request body, filtering out invalid fields.

    Returns:
        Dictionary with valid update fields
    """
    allowed_fields = [
        "start_at",
        "end_at",
        "loop",
        "is_active",
        "assigned_to",
        "contents",
        "playlists",
        "updated_by",
    ]

    update_data = {}

    for field in allowed_fields:
        if field in body:
            if field in ["assigned_to", "contents", "playlists"]:
                # Handle array fields
                arrays = parse_array_fields({field: body[field]})
                update_data[field] = arrays[field]
            else:
                update_data[field] = body[field]

    return update_data


def create_schedules_list_response(schedules: list) -> Dict[str, Any]:
    """
    Create a response with list of schedules.

    Returns:
        Response dictionary with schedules list
    """
    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": "Schedules retrieved successfully",
                "data": schedules,
                "count": len(schedules),
            }
        ),
    }


def create_schedule_response(schedule: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a response with single schedule data.

    Returns:
        Response dictionary with schedule data
    """
    return {
        "statusCode": 200,
        "body": json.dumps(
            {"message": "Schedule retrieved successfully", "data": schedule}
        ),
    }
