import json
import os
import boto3
import uuid
from datetime import datetime
from typing import Dict, Any
from botocore.exceptions import ClientError


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to create the initial superadmin user.
    This should only be called once during initial setup.

    Expected event structure:
    {
        "body": {
            "email": "superadmin@yourcompany.com",
            "first_name": "Super",
            "last_name": "Admin",
            "password": "SecurePass123!"
        }
    }
    """

    try:
        # Get environment variables
        user_pool_id = os.environ.get("USER_POOL_ID")
        users_table_name = os.environ.get("USERS_TABLE_NAME")
        organizations_table_name = os.environ.get("ORGANIZATIONS_TABLE_NAME")

        if not user_pool_id or not users_table_name or not organizations_table_name:
            raise ValueError("Required environment variables not set")

        # Parse request body
        body = json.loads(event.get("body", "{}"))

        # Validate required fields
        required_fields = ["email", "first_name", "last_name", "password"]
        for field in required_fields:
            if field not in body:
                return {
                    "statusCode": 400,
                    "body": json.dumps({"error": f"Missing required field: {field}"}),
                }

        # Create a default organization for the superadmin
        organization_id = str(uuid.uuid4())
        organization_data = {
            "id": organization_id,
            "name": "System Organization",
            "description": "Default organization for system administration",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "created_by": "system",
            "updated_by": "system",
        }

        # Save organization to DynamoDB
        dynamodb = boto3.resource("dynamodb")
        org_table = dynamodb.Table(organizations_table_name)
        org_table.put_item(Item=organization_data)

        # Create Cognito user
        cognito_client = boto3.client("cognito-idp")

        # Create user in Cognito
        cognito_response = cognito_client.admin_create_user(
            UserPoolId=user_pool_id,
            Username=body["email"],
            UserAttributes=[
                {"Name": "email", "Value": body["email"]},
                {"Name": "given_name", "Value": body["first_name"]},
                {"Name": "family_name", "Value": body["last_name"]},
                {"Name": "email_verified", "Value": "true"},
                {"Name": "custom:organization_id", "Value": organization_id},
                {"Name": "custom:role", "Value": "superadmin"},
                {"Name": "custom:created_by", "Value": "system"},
            ],
            TemporaryPassword=body["password"],
            MessageAction="SUPPRESS",  # Don't send welcome email
        )

        # Add user to superadmin group
        cognito_client.admin_add_user_to_group(
            UserPoolId=user_pool_id,
            Username=body["email"],
            GroupName="superadmin",
        )

        # Set permanent password (bypass force change password)
        cognito_client.admin_set_user_password(
            UserPoolId=user_pool_id,
            Username=body["email"],
            Password=body["password"],
            Permanent=True,
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
            "role": "superadmin",
            "organization_id": organization_id,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "created_by": "system",
            "updated_by": "system",
            "status": "CONFIRMED",
        }

        # Save to DynamoDB
        users_table = dynamodb.Table(users_table_name)
        users_table.put_item(Item=user_data)

        return {
            "statusCode": 201,
            "body": json.dumps(
                {
                    "message": "Superadmin created successfully",
                    "user_id": user_id,
                    "organization_id": organization_id,
                    "user": {
                        "id": user_id,
                        "email": body["email"],
                        "first_name": body["first_name"],
                        "last_name": body["last_name"],
                        "role": "superadmin",
                        "organization_id": organization_id,
                        "status": "CONFIRMED",
                    },
                }
            ),
        }

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "UsernameExistsException":
            return {
                "statusCode": 409,
                "body": json.dumps({"error": "Superadmin user already exists"}),
            }
        else:
            print(f"Cognito error: {str(e)}")
            return {
                "statusCode": 500,
                "body": json.dumps({"error": "Failed to create superadmin user"}),
            }
    except Exception as e:
        print(f"Error creating superadmin: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"}),
        }
