import json
import os
import boto3
from typing import Dict, Any
from botocore.exceptions import ClientError


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to refresh JWT access tokens using refresh tokens.

    Expected event structure:
    {
        "body": {
            "refresh_token": "refresh_token_string"
        }
    }
    """

    try:
        print(f"Refresh token event: {json.dumps(event)}")
        # Get environment variables
        user_pool_id = os.environ.get("USER_POOL_ID")
        user_pool_client_id = os.environ.get("USER_POOL_CLIENT_ID")

        if not user_pool_id or not user_pool_client_id:
            raise ValueError("Required environment variables not set")

        # Parse request body
        body = json.loads(event.get("body", "{}"))
        print(f"Request body: {json.dumps(body)}")
        
        # Validate required fields
        if "refresh_token" not in body:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing required field: refresh_token"}),
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Content-Type,Authorization",
                    "Access-Control-Allow-Methods": "POST,OPTIONS",
                },
            }

        refresh_token = body["refresh_token"]
        if not refresh_token:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Refresh token cannot be empty"}),
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Content-Type,Authorization",
                    "Access-Control-Allow-Methods": "POST,OPTIONS",
                },
            }

        # Initialize Cognito client
        cognito_client = boto3.client("cognito-idp")

        # Attempt to refresh the token
        try:
            print(f"Attempting to refresh token")

            refresh_response = cognito_client.initiate_auth(
                ClientId=user_pool_client_id,
                AuthFlow="REFRESH_TOKEN_AUTH",
                AuthParameters={
                    "REFRESH_TOKEN": refresh_token,
                },
            )

            print(f"Refresh response: {json.dumps(refresh_response, default=str)}")

            # Check if refresh was successful
            if "AuthenticationResult" in refresh_response:
                # Token refresh successful
                tokens = refresh_response["AuthenticationResult"]

                return {
                    "statusCode": 200,
                    "body": json.dumps(
                        {
                            "message": "Token refreshed successfully",
                            "access_token": tokens["AccessToken"],
                            "id_token": tokens.get("IdToken"),
                            "expires_in": tokens["ExpiresIn"],
                            "token_type": tokens.get("TokenType", "Bearer"),
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
                    f"Unexpected refresh response: {json.dumps(refresh_response, default=str)}"
                )
                return {
                    "statusCode": 500,
                    "body": json.dumps({"error": "Unexpected token refresh response"}),
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
                    "body": json.dumps({"error": "Invalid or expired refresh token"}),
                    "headers": {
                        "Content-Type": "application/json",
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Headers": "Content-Type,Authorization",
                        "Access-Control-Allow-Methods": "POST,OPTIONS",
                    },
                }
            elif error_code == "TokenRefreshRequiredException":
                return {
                    "statusCode": 401,
                    "body": json.dumps({"error": "Refresh token has expired, re-authentication required"}),
                    "headers": {
                        "Content-Type": "application/json",
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Headers": "Content-Type,Authorization",
                        "Access-Control-Allow-Methods": "POST,OPTIONS",
                    },
                }
            elif error_code == "InvalidParameterException":
                return {
                    "statusCode": 400,
                    "body": json.dumps({"error": "Invalid refresh token format"}),
                    "headers": {
                        "Content-Type": "application/json",
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Headers": "Content-Type,Authorization",
                        "Access-Control-Allow-Methods": "POST,OPTIONS",
                    },
                }
            else:
                print(f"Cognito token refresh error: {str(e)}")
                return {
                    "statusCode": 500,
                    "body": json.dumps(
                        {"error": f"Token refresh failed: {error_code}"}
                    ),
                    "headers": {
                        "Content-Type": "application/json",
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Headers": "Content-Type,Authorization",
                        "Access-Control-Allow-Methods": "POST,OPTIONS",
                    },
                }

    except json.JSONDecodeError as e:
        print(f"JSON decode error: {str(e)}")
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Invalid JSON in request body"}),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,Authorization",
                "Access-Control-Allow-Methods": "POST,OPTIONS",
            },
        }
    except Exception as e:
        print(f"Refresh token error: {str(e)}")
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
