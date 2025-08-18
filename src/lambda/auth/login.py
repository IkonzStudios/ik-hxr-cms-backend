import json
import os
import boto3
from typing import Dict, Any
from botocore.exceptions import ClientError


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to handle user login and return JWT tokens.

    Expected event structure:
    {
        "body": {
            "email": "user@example.com",
            "password": "userpassword"
        }
    }
    """

    try:
        print(f"Login event: {json.dumps(event)}")

        # Get environment variables
        user_pool_id = os.environ.get("USER_POOL_ID")
        user_pool_client_id = os.environ.get("USER_POOL_CLIENT_ID")

        print(f"User Pool ID: {user_pool_id}")
        print(f"Client ID: {user_pool_client_id}")

        if not user_pool_id or not user_pool_client_id:
            raise ValueError("Required environment variables not set")

        # Parse request body
        body = json.loads(event.get("body", "{}"))
        print(f"Request body: {json.dumps(body)}")

        # Validate required fields
        required_fields = ["email", "password"]
        for field in required_fields:
            if field not in body:
                return {
                    "statusCode": 400,
                    "body": json.dumps({"error": f"Missing required field: {field}"}),
                    "headers": {
                        "Content-Type": "application/json",
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Headers": "Content-Type,Authorization",
                        "Access-Control-Allow-Methods": "POST,OPTIONS",
                    },
                }

        # Initialize Cognito client
        cognito_client = boto3.client("cognito-idp")

        # Attempt to authenticate user
        try:
            print(f"Attempting authentication for user: {body['email']}")

            auth_response = cognito_client.admin_initiate_auth(
                UserPoolId=user_pool_id,
                ClientId=user_pool_client_id,
                AuthFlow="ADMIN_USER_PASSWORD_AUTH",
                AuthParameters={
                    "USERNAME": body["email"],
                    "PASSWORD": body["password"],
                },
            )

            print(f"Auth response: {json.dumps(auth_response, default=str)}")

            # Check if authentication was successful
            if auth_response.get("ChallengeName") == "NEW_PASSWORD_REQUIRED":
                # User needs to change password (first time login)
                return {
                    "statusCode": 200,
                    "body": json.dumps(
                        {
                            "message": "Password change required",
                            "challenge": "NEW_PASSWORD_REQUIRED",
                            "session": auth_response["Session"],
                            "user_id": auth_response.get("ChallengeParameters", {}).get(
                                "USER_ID_FOR_SRP", ""
                            ),
                        }
                    ),
                    "headers": {
                        "Content-Type": "application/json",
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Headers": "Content-Type,Authorization",
                        "Access-Control-Allow-Methods": "POST,OPTIONS",
                    },
                }
            elif "AuthenticationResult" in auth_response:
                # Authentication successful
                tokens = auth_response["AuthenticationResult"]

                # Get user details
                user_info = cognito_client.admin_get_user(
                    UserPoolId=user_pool_id, Username=body["email"]
                )

                # Extract user attributes
                user_attributes = {
                    attr["Name"]: attr["Value"] for attr in user_info["UserAttributes"]
                }

                return {
                    "statusCode": 200,
                    "body": json.dumps(
                        {
                            "message": "Login successful",
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
                            },
                        }
                    ),
                    "headers": {
                        "Content-Type": "application/json",
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Headers": "Content-Type,Authorization",
                        "Access-Control-Allow-Methods": "POST,OPTIONS",
                    },
                }
            else:
                # Unexpected response
                print(
                    f"Unexpected auth response: {json.dumps(auth_response, default=str)}"
                )
                return {
                    "statusCode": 500,
                    "body": json.dumps({"error": "Unexpected authentication response"}),
                    "headers": {
                        "Content-Type": "application/json",
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Headers": "Content-Type,Authorization",
                        "Access-Control-Allow-Methods": "POST,OPTIONS",
                    },
                }

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            print(f"Cognito ClientError: {error_code} - {str(e)}")

            if error_code == "NotAuthorizedException":
                return {
                    "statusCode": 401,
                    "body": json.dumps({"error": "Invalid email or password"}),
                    "headers": {
                        "Content-Type": "application/json",
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Headers": "Content-Type,Authorization",
                        "Access-Control-Allow-Methods": "POST,OPTIONS",
                    },
                }
            elif error_code == "UserNotConfirmedException":
                return {
                    "statusCode": 401,
                    "body": json.dumps({"error": "User account not confirmed"}),
                    "headers": {
                        "Content-Type": "application/json",
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Headers": "Content-Type,Authorization",
                        "Access-Control-Allow-Methods": "POST,OPTIONS",
                    },
                }
            elif error_code == "UserNotFoundException":
                return {
                    "statusCode": 401,
                    "body": json.dumps({"error": "User not found"}),
                    "headers": {
                        "Content-Type": "application/json",
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Headers": "Content-Type,Authorization",
                        "Access-Control-Allow-Methods": "POST,OPTIONS",
                    },
                }
            else:
                print(f"Cognito authentication error: {str(e)}")
                return {
                    "statusCode": 500,
                    "body": json.dumps(
                        {"error": f"Authentication failed: {error_code}"}
                    ),
                    "headers": {
                        "Content-Type": "application/json",
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Headers": "Content-Type,Authorization",
                        "Access-Control-Allow-Methods": "POST,OPTIONS",
                    },
                }

    except Exception as e:
        print(f"Login error: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"Internal server error: {str(e)}"}),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,Authorization",
                "Access-Control-Allow-Methods": "POST,OPTIONS",
            },
        }
