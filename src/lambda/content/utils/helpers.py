import json
import boto3
import uuid
from datetime import datetime
from typing import Dict, Any, Tuple, Optional
from .constants import REQUIRED_CONTENT_FIELDS


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
    for field in REQUIRED_CONTENT_FIELDS:
        if not body.get(field["column_name"]):
            return {
                "statusCode": 400,
                "body": json.dumps({"error": f'{field["name"]} is required'}),
            }
    return None


def parse_array_fields(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse stringified array fields (assigned_to, playlists) from the body.

    Returns:
        Dictionary with parsed array values
    """
    result = {}

    for field_name in ["assigned_to", "playlists"]:
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


def create_content_data(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create the content data dictionary from the request body.

    Returns:
        Complete content data dictionary ready for DynamoDB
    """
    # Parse array fields
    arrays = parse_array_fields(body)

    # Generate content ID and timestamps
    content_id = str(uuid.uuid4())
    current_time = datetime.now().isoformat()

    # Create content data dictionary
    content_data = {
        "id": content_id,
        "url": body["url"],
        "thumbnail": body.get("thumbnail", ""),
        "title": body["title"],
        "description": body.get("description", ""),
        "is_active": body.get("is_active", True),
        "is_deleted": body.get("is_deleted", False),
        "assigned_to": arrays["assigned_to"],
        "playlists": arrays["playlists"],
        "organization_id": body["organization_id"],
        "created_at": current_time,
        "updated_at": current_time,
        "created_by": body.get("created_by", ""),
        "updated_by": body.get("updated_by", ""),
    }

    return content_data


def save_content_to_db(
    content_data: Dict[str, Any], table_name: str
) -> Optional[Dict[str, Any]]:
    """
    Save content data to DynamoDB.

    Returns:
        None if successful, error response dict if failed
    """
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)

        table.put_item(
            Item=content_data, ConditionExpression="attribute_not_exists(id)"
        )
        return None

    except Exception as e:
        print(f"Error creating content: {str(e)}")
        print(f"Error type: {type(e)}")
        print(f"Error message: {str(e)}")
        return {
            "statusCode": 409,
            "body": json.dumps({"error": "Content with this ID already exists"}),
        }


def create_success_response(content_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a success response with content data.

    Returns:
        Success response dictionary
    """
    return {
        "statusCode": 201,
        "body": json.dumps(
            {"message": "Content created successfully", "data": content_data}
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


def get_content_by_id_from_db(
    content_id: str, table_name: str
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Get content by ID from DynamoDB.

    Returns:
        Tuple of (content_data, error_response)
        If successful: (content_dict, None)
        If error: (None, error_response_dict)
    """
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)

        response = table.get_item(Key={"id": content_id})

        if "Item" not in response:
            return None, {
                "statusCode": 404,
                "body": json.dumps({"error": "Content not found"}),
            }

        return response["Item"], None

    except Exception as e:
        print(f"Error getting content: {str(e)}")
        return None, {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"}),
        }


def get_contents_by_org_id_from_db(
    org_id: str, table_name: str
) -> Tuple[Optional[list], Optional[Dict[str, Any]]]:
    """
    Get all contents by organization ID from DynamoDB.

    Returns:
        Tuple of (contents_list, error_response)
        If successful: (contents_list, None)
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
        print(f"Error getting contents by organization ID: {str(e)}")
        return None, {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"}),
        }


def update_content_in_db(
    content_id: str, update_data: Dict[str, Any], table_name: str
) -> Optional[Dict[str, Any]]:
    """
    Update content in DynamoDB.

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
            Key={"id": content_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values,
            ExpressionAttributeNames=expression_attribute_names
            if expression_attribute_names
            else None,
            ConditionExpression="attribute_exists(id)",
        )

        return None

    except Exception as e:
        print(f"Error updating content: {str(e)}")
        if "ConditionalCheckFailedException" in str(e):
            return {
                "statusCode": 404,
                "body": json.dumps({"error": "Content not found"}),
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
        "url",
        "thumbnail",
        "title",
        "description",
        "is_active",
        "is_deleted",
        "assigned_to",
        "playlists",
        "updated_by",
    ]

    update_data = {}

    for field in allowed_fields:
        if field in body:
            if field in ["assigned_to", "playlists"]:
                # Handle array fields
                arrays = parse_array_fields({field: body[field]})
                update_data[field] = arrays[field]
            else:
                update_data[field] = body[field]

    return update_data


def create_contents_list_response(contents: list) -> Dict[str, Any]:
    """
    Create a response with list of contents.

    Returns:
        Response dictionary with contents list
    """
    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": "Contents retrieved successfully",
                "data": contents,
                "count": len(contents),
            }
        ),
    }


def create_content_response(content: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a response with single content data.

    Returns:
        Response dictionary with content data
    """
    return {
        "statusCode": 200,
        "body": json.dumps(
            {"message": "Content retrieved successfully", "data": content}
        ),
    }
