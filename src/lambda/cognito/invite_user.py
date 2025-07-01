import json
import os
import boto3
from datetime import datetime
from typing import Dict, Any
from botocore.exceptions import ClientError


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to invite a user to the organization.

    Expected event structure:
    {
        "body": {
            "email": "user@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "role": "user",
            "organization_id": "org-123",
            "invited_by": "admin-456"
        }
    }
    """

    try:
        # Get environment variables
        user_pool_id = os.environ.get("USER_POOL_ID")
        users_table_name = os.environ.get("USERS_TABLE_NAME")

        if not user_pool_id or not users_table_name:
            raise ValueError("Required environment variables not set")

        # Parse request body
        body = json.loads(event.get("body", "{}"))

        # Validate required fields
        required_fields = [
            "email",
            "first_name",
            "last_name",
            "role",
            "organization_id",
            "invited_by",
        ]
        for field in required_fields:
            if field not in body:
                return {
                    "statusCode": 400,
                    "body": json.dumps({"error": f"Missing required field: {field}"}),
                }

        # Create Cognito user
        cognito_client = boto3.client("cognito-idp")

        # Generate temporary password
        temp_password = generate_temp_password()

        # Create user in Cognito
        cognito_response = cognito_client.admin_create_user(
            UserPoolId=user_pool_id,
            Username=body["email"],
            UserAttributes=[
                {"Name": "email", "Value": body["email"]},
                {"Name": "given_name", "Value": body["first_name"]},
                {"Name": "family_name", "Value": body["last_name"]},
                {"Name": "email_verified", "Value": "true"},
                {"Name": "custom:organization_id", "Value": body["organization_id"]},
                {"Name": "custom:role", "Value": body["role"]},
                {"Name": "custom:created_by", "Value": body["invited_by"]},
            ],
            TemporaryPassword=temp_password,
            MessageAction="SUPPRESS",  # Don't send welcome email automatically
        )

        # Add user to appropriate group
        cognito_client.admin_add_user_to_group(
            UserPoolId=user_pool_id,
            Username=body["email"],
            GroupName=body["role"],
        )

        # Create user record in DynamoDB
        user_id = cognito_response["User"]["Username"]
        user_data = {
            "id": user_id,
            "cognito_sub": cognito_response["User"]["Attributes"][0][
                "Value"
            ],  # sub attribute
            "first_name": body["first_name"],
            "last_name": body["last_name"],
            "email": body["email"].lower(),
            "role": body["role"],
            "organization_id": body["organization_id"],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "created_by": body["invited_by"],
            "updated_by": body["invited_by"],
            "status": "FORCE_CHANGE_PASSWORD",
        }

        # Save to DynamoDB
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(users_table_name)
        table.put_item(Item=user_data)

        # TODO: Send invitation email with temporary password
        # This would typically be done through SES or another email service

        return {
            "statusCode": 201,
            "body": json.dumps(
                {
                    "message": "User invited successfully",
                    "user_id": user_id,
                    "temporary_password": temp_password,
                    "user": {
                        "id": user_id,
                        "email": body["email"],
                        "first_name": body["first_name"],
                        "last_name": body["last_name"],
                        "role": body["role"],
                        "organization_id": body["organization_id"],
                        "status": "FORCE_CHANGE_PASSWORD",
                    },
                }
            ),
        }

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "UsernameExistsException":
            return {
                "statusCode": 409,
                "body": json.dumps({"error": "User with this email already exists"}),
            }
        else:
            print(f"Cognito error: {str(e)}")
            return {
                "statusCode": 500,
                "body": json.dumps({"error": "Failed to invite user"}),
            }
    except Exception as e:
        print(f"Error inviting user: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"}),
        }


def generate_temp_password() -> str:
    """Generate a temporary password that meets Cognito requirements."""
    import random
    import string

    # Generate password with required characters
    lowercase = "".join(random.choices(string.ascii_lowercase, k=2))
    uppercase = "".join(random.choices(string.ascii_uppercase, k=2))
    digits = "".join(random.choices(string.digits, k=2))
    symbols = "".join(random.choices("!@#$%^&*", k=2))

    password = lowercase + uppercase + digits + symbols
    password_list = list(password)
    random.shuffle(password_list)

    return "".join(password_list)
