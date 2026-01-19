import json
import os
import boto3
import uuid
from datetime import datetime
from typing import Dict, Any
from botocore.exceptions import ClientError


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


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to create a user in Cognito User Pool.

    Expected event structure:
    {
        "body": {
            "email": "user@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "role": "user",
            "organization_id: "",
            // For superadmin users creating a new organization:
            "organization_name": "Acme Corp", 
            "organization_license": "LICENSE-123"
            // For admin users, their organization_id is used automatically
        },
        "requestContext": {
            "authorizer": {
                "user_id": "current-user-id",
                "role": "superadmin|admin",
                "organization_id": "current-user-org-id"
            }
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

        # Extract current user context from authorizer
        request_context = event.get("requestContext", {})
        authorizer = request_context.get("authorizer", {})
        
        current_user_id = authorizer.get("user_id")
        current_user_role = authorizer.get("role")
        current_user_org_id = authorizer.get("organization_id")

        if not current_user_id or not current_user_role:
            return {
                "statusCode": 401,
                "headers": get_cors_headers(),
                "body": json.dumps({"error": "Unauthorized: Invalid user context"}),
            }

        # Parse request body
        body = json.loads(event.get("body", "{}"))

        # Validate required fields
        required_fields = [
            "email",
            "first_name",
            "last_name",
            "role",
        ]
        for field in required_fields:
            if field not in body:
                return {
                    "statusCode": 400,
                    "headers": get_cors_headers(),
                    "body": json.dumps({"error": f"Missing required field: {field}"}),
                }

        # Determine organization_id based on current user's role
        if current_user_role == "superadmin":
            # For superadmin, create a new organization if not provided
            if "organization_id" in body:
                organization_id = body["organization_id"]
            elif "organization_name" in body and "organization_license" in body:
                organization_id = str(uuid.uuid4())
                # Create new organization
                current_time = datetime.now().isoformat()
                organization_data = {
                    "id": organization_id,
                    "name": body["organization_name"],
                    "license": body["organization_license"],
                    "created_at": current_time,
                    "updated_at": current_time,
                    "created_by": current_user_id,
                    "updated_by": current_user_id,
                }
                 # Save organization to DynamoDB
                dynamodb = boto3.resource("dynamodb")
                organizations_table = dynamodb.Table(organizations_table_name)
                
                organizations_table.put_item(
                    Item=organization_data,
                    ConditionExpression="attribute_not_exists(id)"
                )
            else:
                return {
                    "statusCode": 400,
                    "headers": get_cors_headers(),
                    "body": json.dumps({"error": "Superadmin must provide organization_name and organization_license"}),
                }
            
            body["organization_id"] = organization_id
            
        elif current_user_role == "admin":
            if body["role"] == "superadmin":
                return {
                    "statusCode": 498,
                    "headers": get_cors_headers(),
                    "body": json.dumps({"error": "Admin users cannot create superadmin users"}),
                }
            
            # For admin, use their organization_id
            if not current_user_org_id:
                return {
                    "statusCode": 400,
                    "headers": get_cors_headers(),
                    "body": json.dumps({"error": "Admin user must have an organization_id"}),
                }
            body["organization_id"] = current_user_org_id
        else:
            return {
                "statusCode": 498,
                "headers": get_cors_headers(),
                "body": json.dumps({"error": "Only superadmin and admin users can create users"}),
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
                {"Name": "custom:created_by", "Value": current_user_id},
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
            "created_by": current_user_id,
            "updated_by": current_user_id,
            "status": "FORCE_CHANGE_PASSWORD",
        }

        # Save to DynamoDB
        dynamodb = boto3.resource("dynamodb")
        users_table = dynamodb.Table(users_table_name)
        users_table.put_item(Item=user_data)

        # TODO: Send invitation email with temporary password
        # This would typically be done through SES or another email service
        # Include organization details in the email for superadmin created users

        return {
            "statusCode": 201,
            "headers": get_cors_headers(),
            "body": json.dumps(
                {
                    "message": "User created successfully",
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
                "headers": get_cors_headers(),
                "body": json.dumps({"error": "User with this email already exists"}),
            }
        else:
            print(f"Cognito error: {str(e)}")
            return {
                "statusCode": 500,
                "headers": get_cors_headers(),
                "body": json.dumps({"error": "Failed to create user in Cognito"}),
            }
    except Exception as e:
        print(f"Error creating user: {str(e)}")
        return {
            "statusCode": 500,
            "headers": get_cors_headers(),
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

    # Combine and shuffle
    password = lowercase + uppercase + digits + symbols
    password_list = list(password)
    random.shuffle(password_list)

    return "".join(password_list)
