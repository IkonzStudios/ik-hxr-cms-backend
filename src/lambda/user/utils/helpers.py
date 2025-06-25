import json
import boto3
import uuid
import hashlib
import re
from datetime import datetime
from typing import Dict, Any, Tuple, Optional
from .constants import REQUIRED_USER_FIELDS, VALID_USER_ROLES


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
    for field in REQUIRED_USER_FIELDS:
        if not body.get(field["column_name"]):
            return {
                "statusCode": 400,
                "body": json.dumps({"error": f'{field["name"]} is required'}),
            }
    return None


def validate_email_format(email: str) -> Optional[Dict[str, Any]]:
    """
    Validate email format using regex.

    Returns:
        None if valid, error response dict if invalid
    """
    email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(email_pattern, email):
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Invalid email format"}),
        }
    return None


def validate_password_strength(password: str) -> Optional[Dict[str, Any]]:
    """
    Validate password strength (minimum 8 characters, at least one letter and one number).

    Returns:
        None if valid, error response dict if invalid
    """
    if len(password) < 8:
        return {
            "statusCode": 400,
            "body": json.dumps(
                {"error": "Password must be at least 8 characters long"}
            ),
        }

    if not re.search(r"[A-Za-z]", password):
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Password must contain at least one letter"}),
        }

    if not re.search(r"\d", password):
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Password must contain at least one number"}),
        }

    return None


def validate_user_role(role: str) -> Optional[Dict[str, Any]]:
    """
    Validate that the user role is valid.

    Returns:
        None if valid, error response dict if invalid
    """
    if role not in VALID_USER_ROLES:
        return {
            "statusCode": 400,
            "body": json.dumps(
                {
                    "error": f"Invalid role. Must be one of: {', '.join(VALID_USER_ROLES)}"
                }
            ),
        }
    return None


def hash_password(password: str) -> str:
    """
    Hash password using SHA-256.

    Returns:
        Hashed password string
    """
    return hashlib.sha256(password.encode()).hexdigest()


def create_user_data(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create the user data dictionary from the request body.

    Returns:
        Complete user data dictionary ready for DynamoDB
    """
    # Generate user ID and timestamps
    user_id = str(uuid.uuid4())
    current_time = datetime.now().isoformat()

    # Hash the password
    hashed_password = hash_password(body["password"])

    # Create user data dictionary
    user_data = {
        "id": user_id,
        "first_name": body["first_name"],
        "last_name": body["last_name"],
        "email": body["email"].lower(),  # Store email in lowercase
        "role": body["role"],
        "password": hashed_password,
        "organization_id": body["organization_id"],
        "created_at": current_time,
        "updated_at": current_time,
        "created_by": body.get("created_by", ""),
        "updated_by": body.get("updated_by", ""),
    }

    return user_data


def save_user_to_db(
    user_data: Dict[str, Any], table_name: str
) -> Optional[Dict[str, Any]]:
    """
    Save user data to DynamoDB.

    Returns:
        None if successful, error response dict if failed
    """
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)

        # Check if email already exists
        email_response = table.scan(
            FilterExpression="email = :email",
            ExpressionAttributeValues={":email": user_data["email"]},
        )

        if email_response["Items"]:
            return {
                "statusCode": 409,
                "body": json.dumps({"error": "User with this email already exists"}),
            }

        table.put_item(Item=user_data, ConditionExpression="attribute_not_exists(id)")
        return None

    except Exception as e:
        print(f"Error creating user: {str(e)}")
        print(f"Error type: {type(e)}")
        print(f"Error message: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"}),
        }


def create_success_response(user_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a success response with user data (excluding password).

    Returns:
        Success response dictionary
    """
    # Remove password from response
    response_data = user_data.copy()
    response_data.pop("password", None)

    return {
        "statusCode": 201,
        "body": json.dumps(
            {"message": "User created successfully", "data": response_data}
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


def get_user_by_id_from_db(
    user_id: str, table_name: str
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Get user by ID from DynamoDB.

    Returns:
        Tuple of (user_data, error_response)
        If successful: (user_dict, None)
        If error: (None, error_response_dict)
    """
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)

        response = table.get_item(Key={"id": user_id})

        if "Item" not in response:
            return None, {
                "statusCode": 404,
                "body": json.dumps({"error": "User not found"}),
            }

        return response["Item"], None

    except Exception as e:
        print(f"Error getting user: {str(e)}")
        return None, {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"}),
        }


def get_users_by_org_id_from_db(
    org_id: str, table_name: str
) -> Tuple[Optional[list], Optional[Dict[str, Any]]]:
    """
    Get all users by organization ID from DynamoDB.

    Returns:
        Tuple of (users_list, error_response)
        If successful: (users_list, None)
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
        print(f"Error getting users by organization ID: {str(e)}")
        return None, {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"}),
        }


def update_user_in_db(
    user_id: str, update_data: Dict[str, Any], table_name: str
) -> Optional[Dict[str, Any]]:
    """
    Update user in DynamoDB.

    Returns:
        None if successful, error response dict if failed
    """
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)

        # If email is being updated, check for uniqueness
        if "email" in update_data:
            email_response = table.query(
                IndexName="email-index",
                KeyConditionExpression="email = :email",
                ExpressionAttributeValues={":email": update_data["email"].lower()},
            )

            # Check if email exists for a different user
            for item in email_response["Items"]:
                if item["id"] != user_id:
                    return {
                        "statusCode": 409,
                        "body": json.dumps(
                            {"error": "User with this email already exists"}
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
            elif key == "email":
                # Store email in lowercase
                attr_name = f"#{key}"
                attr_value = f":{key}"
                expression_attribute_names[attr_name] = key
                expression_attribute_values[attr_value] = value.lower()
                update_expression += f"{attr_name} = {attr_value}, "
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
            Key={"id": user_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values,
            ExpressionAttributeNames=expression_attribute_names
            if expression_attribute_names
            else None,
            ConditionExpression="attribute_exists(id)",
        )

        return None

    except Exception as e:
        print(f"Error updating user: {str(e)}")
        if "ConditionalCheckFailedException" in str(e):
            return {
                "statusCode": 404,
                "body": json.dumps({"error": "User not found"}),
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
        "first_name",
        "last_name",
        "email",
        "role",
        "password",
        "updated_by",
    ]

    update_data = {}

    for field in allowed_fields:
        if field in body:
            if field == "password":
                # Hash the password before storing
                update_data[field] = hash_password(body[field])
            else:
                update_data[field] = body[field]

    return update_data


def create_users_list_response(users: list) -> Dict[str, Any]:
    """
    Create a response with list of users (excluding passwords).

    Returns:
        Response dictionary with users list
    """
    # Remove passwords from all users
    safe_users = []
    for user in users:
        safe_user = user.copy()
        safe_user.pop("password", None)
        safe_users.append(safe_user)

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": "Users retrieved successfully",
                "data": safe_users,
                "count": len(safe_users),
            }
        ),
    }


def create_user_response(user: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a response with single user data (excluding password).

    Returns:
        Response dictionary with user data
    """
    # Remove password from response
    safe_user = user.copy()
    safe_user.pop("password", None)

    return {
        "statusCode": 200,
        "body": json.dumps(
            {"message": "User retrieved successfully", "data": safe_user}
        ),
    }
