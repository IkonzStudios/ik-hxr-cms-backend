import json
import boto3
import uuid
from datetime import datetime
from typing import Dict, Any, Tuple, Optional
from .constants import REQUIRED_ORGANIZATION_FIELDS


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
    for field in REQUIRED_ORGANIZATION_FIELDS:
        if not body.get(field["column_name"]):
            return {
                "statusCode": 400,
                "body": json.dumps({"error": f'{field["name"]} is required'}),
            }
    return None


def create_organization_data(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create the organization data dictionary from the request body.

    Returns:
        Complete organization data dictionary ready for DynamoDB
    """
    # Generate organization ID and timestamps
    organization_id = str(uuid.uuid4())
    current_time = datetime.now().isoformat()

    # Create organization data dictionary
    organization_data = {
        "id": organization_id,
        "name": body["name"],
        "license": body["license"],
        "created_at": current_time,
        "updated_at": current_time,
        "created_by": body.get("created_by", ""),
        "updated_by": body.get("updated_by", ""),
    }

    return organization_data


def save_organization_to_db(
    organization_data: Dict[str, Any], table_name: str
) -> Optional[Dict[str, Any]]:
    """
    Save organization data to DynamoDB.

    Returns:
        None if successful, error response dict if failed
    """
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)

        # Check if license already exists
        license_response = table.scan(
            FilterExpression="license = :license",
            ExpressionAttributeValues={":license": organization_data["license"]},
        )

        if license_response["Items"]:
            return {
                "statusCode": 409,
                "body": json.dumps(
                    {"error": "Organization with this license already exists"}
                ),
            }

        table.put_item(
            Item=organization_data, ConditionExpression="attribute_not_exists(id)"
        )
        return None

    except Exception as e:
        print(f"Error creating organization: {str(e)}")
        print(f"Error type: {type(e)}")
        print(f"Error message: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"}),
        }


def create_success_response(organization_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a success response with organization data.

    Returns:
        Success response dictionary
    """
    return {
        "statusCode": 201,
        "body": json.dumps(
            {"message": "Organization created successfully", "data": organization_data}
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


def get_organization_by_id_from_db(
    organization_id: str, table_name: str
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Get organization by ID from DynamoDB.

    Returns:
        Tuple of (organization_data, error_response)
        If successful: (organization_dict, None)
        If error: (None, error_response_dict)
    """
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)

        response = table.get_item(Key={"id": organization_id})

        if "Item" not in response:
            return None, {
                "statusCode": 404,
                "body": json.dumps({"error": "Organization not found"}),
            }

        return response["Item"], None

    except Exception as e:
        print(f"Error getting organization: {str(e)}")
        return None, {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"}),
        }


def get_all_organizations_from_db(
    table_name: str,
) -> Tuple[Optional[list], Optional[Dict[str, Any]]]:
    """
    Get all organizations from DynamoDB.

    Returns:
        Tuple of (organizations_list, error_response)
        If successful: (organizations_list, None)
        If error: (None, error_response_dict)
    """
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)

        response = table.scan()
        return response["Items"], None

    except Exception as e:
        print(f"Error getting all organizations: {str(e)}")
        return None, {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"}),
        }


def update_organization_in_db(
    organization_id: str, update_data: Dict[str, Any], table_name: str
) -> Optional[Dict[str, Any]]:
    """
    Update organization in DynamoDB.

    Returns:
        None if successful, error response dict if failed
    """
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)

        # If license is being updated, check for uniqueness
        if "license" in update_data:
            license_response = table.scan(
                FilterExpression="license = :license",
                ExpressionAttributeValues={":license": update_data["license"]},
            )

            # Check if license exists for a different organization
            for item in license_response["Items"]:
                if item["id"] != organization_id:
                    return {
                        "statusCode": 409,
                        "body": json.dumps(
                            {"error": "Organization with this license already exists"}
                        ),
                    }

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
            Key={"id": organization_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values,
            ExpressionAttributeNames=expression_attribute_names
            if expression_attribute_names
            else None,
            ConditionExpression="attribute_exists(id)",
        )

        return None

    except Exception as e:
        print(f"Error updating organization: {str(e)}")
        if "ConditionalCheckFailedException" in str(e):
            return {
                "statusCode": 404,
                "body": json.dumps({"error": "Organization not found"}),
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
        "name",
        "license",
        "updated_by",
    ]

    update_data = {}

    for field in allowed_fields:
        if field in body:
            update_data[field] = body[field]

    return update_data


def create_organizations_list_response(organizations: list) -> Dict[str, Any]:
    """
    Create a response with list of organizations.

    Returns:
        Response dictionary with organizations list
    """
    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": "Organizations retrieved successfully",
                "data": organizations,
                "count": len(organizations),
            }
        ),
    }


def create_organization_response(organization: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a response with single organization data.

    Returns:
        Response dictionary with organization data
    """
    return {
        "statusCode": 200,
        "body": json.dumps(
            {"message": "Organization retrieved successfully", "data": organization}
        ),
    }
