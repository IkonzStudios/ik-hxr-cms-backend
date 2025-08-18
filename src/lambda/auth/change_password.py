import json
import os
import boto3
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
    Lambda function to handle password change for new users.

    Expected event structure:
    {
        "body": {
            "email": "user@example.com",
            "new_password": "NewSecurePass123!",
            "session": "session_token_from_login"
        }
    }
    """

    try:
        # Get environment variables
        user_pool_id = os.environ.get("USER_POOL_ID")
        user_pool_client_id = os.environ.get("USER_POOL_CLIENT_ID")

        if not user_pool_id or not user_pool_client_id:
            raise ValueError("Required environment variables not set")

        # Parse request body
        body = json.loads(event.get("body", "{}"))

        # Validate required fields
        required_fields = ["email", "new_password", "session"]
        for field in required_fields:
            if field not in body:
                return {
                    "statusCode": 400,
                    "headers": get_cors_headers(),
                    "body": json.dumps({"error": f"Missing required field: {field}"}),
                }

        # Initialize Cognito client
        cognito_client = boto3.client("cognito-idp")

        # Respond to the NEW_PASSWORD_REQUIRED challenge
        try:
            auth_response = cognito_client.admin_respond_to_auth_challenge(
                UserPoolId=user_pool_id,
                ClientId=user_pool_client_id,
                ChallengeName="NEW_PASSWORD_REQUIRED",
                Session=body["session"],
                ChallengeResponses={
                    "USERNAME": body["email"],
                    "NEW_PASSWORD": body["new_password"],
                },
            )

            # Check if password change was successful
            if "AuthenticationResult" in auth_response:
                tokens = auth_response["AuthenticationResult"]

                # Get user details
                user_info = cognito_client.admin_get_user(
                    UserPoolId=user_pool_id, Username=body["email"]
                )

                # Extract user attributes
                user_attributes = {
                    attr["Name"]: attr["Value"] for attr in user_info["UserAttributes"]
                }

                # Update user status in DynamoDB
                users_table_name = os.environ.get("USERS_TABLE_NAME")
                if users_table_name:
                    try:
                        dynamodb = boto3.resource("dynamodb")
                        users_table = dynamodb.Table(users_table_name)
                        
                        # Update user status to CONFIRMED
                        users_table.update_item(
                            Key={
                                "id": user_attributes.get("sub")  # Use the cognito sub as the user ID
                            },
                            UpdateExpression="SET #status = :status, updated_at = :updated_at",
                            ExpressionAttributeNames={
                                "#status": "status"
                            },
                            ExpressionAttributeValues={
                                ":status": "CONFIRMED",
                                ":updated_at": datetime.now().isoformat()
                            }
                        )
                        print(f"User status updated to CONFIRMED for user: {body['email']}")
                    except Exception as e:
                        print(f"Error updating user status: {str(e)}")
                        # Don't fail the password change if DynamoDB update fails
                
                return {
                    "statusCode": 200,
                    "headers": get_cors_headers(),
                    "body": json.dumps(
                        {
                            "message": "Password changed successfully",
                            "access_token": tokens["AccessToken"],
                            "id_token": tokens["IdToken"],
                            "refresh_token": tokens.get("RefreshToken"),
                            "expires_in": tokens["ExpiresIn"],
                            "user": {
                                "email": user_attributes.get("email"),
                                "first_name": user_attributes.get("given_name"),
                                "last_name": user_attributes.get("family_name"),
                                "role": user_attributes.get("custom:role", "user"),
                                "organization_id": user_attributes.get(
                                    "custom:organization_id"
                                ),
                                "status": "CONFIRMED",  # ← Add this to response
                            },
                        }
                    ),
                }

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "NotAuthorizedException":
                return {
                    "statusCode": 401,
                    "headers": get_cors_headers(),
                    "body": json.dumps({"error": "Invalid session or credentials"}),
                }
            elif error_code == "InvalidPasswordException":
                return {
                    "statusCode": 400,
                    "headers": get_cors_headers(),
                    "body": json.dumps(
                        {"error": "Password does not meet requirements"}
                    ),
                }
            else:
                print(f"Password change error: {str(e)}")
                return {
                    "statusCode": 500,
                    "headers": get_cors_headers(),
                    "body": json.dumps({"error": "Password change failed"}),
                }

    except Exception as e:
        print(f"Password change error: {str(e)}")
        return {
            "statusCode": 500,
            "headers": get_cors_headers(),
            "body": json.dumps({"error": "Internal server error"}),
        }
