import json
import os
import boto3
import base64
from typing import Dict, Any
from botocore.exceptions import ClientError


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to authorize API Gateway requests using Cognito JWT tokens.

    Expected event structure:
    {
        "type": "TOKEN",
        "authorizationToken": "Bearer <jwt_token>",
        "methodArn": "arn:aws:execute-api:region:account:api-id/stage/HTTP-VERB/resource"
    }
    """

    # Add immediate logging
    print("=== LAMBDA AUTHORIZER INVOKED ===")
    print(f"Function Name: {context.function_name}")
    print(f"Request ID: {context.aws_request_id}")
    print(f"Event: {json.dumps(event, default=str)}")
    print("==================================")

    try:
        # Get environment variables
        user_pool_id = os.environ.get("USER_POOL_ID")
        user_pool_client_id = os.environ.get("USER_POOL_CLIENT_ID")

        print(f"User Pool ID: {user_pool_id}")
        print(f"Client ID: {user_pool_client_id}")

        if not user_pool_id or not user_pool_client_id:
            print("ERROR: Required environment variables not set")
            raise ValueError("Required environment variables not set")

        # Extract token from authorization header
        auth_token = event.get("authorizationToken", "")
        print(
            f"Authorization Token: {auth_token[:50]}..."
            if len(auth_token) > 50
            else f"Authorization Token: {auth_token}"
        )

        if not auth_token.startswith("Bearer "):
            print("ERROR: Token does not start with 'Bearer '")
            return generate_policy("user", "Deny", event["methodArn"])

        token = auth_token.split(" ")[1]
        print(
            f"Extracted Token: {token[:50]}..."
            if len(token) > 50
            else f"Extracted Token: {token}"
        )

        # For testing purposes, decode the token without verification
        # In production, you should implement proper verification
        try:
            # Decode the JWT token (without verification for now)
            parts = token.split(".")
            if len(parts) != 3:
                print("ERROR: Invalid JWT token format")
                return generate_policy("user", "Deny", event["methodArn"])

            # Decode the payload
            payload = parts[1]
            # Add padding if needed
            payload += "=" * (4 - len(payload) % 4)
            decoded_payload = base64.b64decode(payload).decode("utf-8")
            user_info = json.loads(decoded_payload)

            print(f"Decoded token payload: {json.dumps(user_info, default=str)}")

            # Extract user information
            user_id = user_info.get("sub")
            email = user_info.get("email")
            role = user_info.get("custom:role", "user")
            organization_id = user_info.get("custom:organization_id", "")

            print(
                f"Extracted user info - ID: {user_id}, Email: {email}, Role: {role}, Org: {organization_id}"
            )

            # Create context for the policy
            context_data = {
                "user_id": user_id,
                "email": email,
                "role": role,
                "organization_id": organization_id,
            }

            print(f"Generated context: {json.dumps(context_data)}")

            # Generate allow policy with user context
            policy = generate_policy(user_id, "Allow", event["methodArn"], context_data)
            print(f"Generated policy: {json.dumps(policy, default=str)}")

            return policy

        except Exception as e:
            print(f"Token decoding error: {str(e)}")
            return generate_policy("user", "Deny", event["methodArn"])

    except Exception as e:
        print(f"Authorization error: {str(e)}")
        import traceback

        print(f"Traceback: {traceback.format_exc()}")
        return generate_policy("user", "Deny", event["methodArn"])


def generate_policy(
    principal_id: str, effect: str, resource: str, context: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Generate an IAM policy document for API Gateway authorization."""

    policy = {
        "principalId": principal_id,
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": effect,
                    "Resource": resource,
                }
            ],
        },
    }

    if context:
        policy["context"] = context

    print(f"Generated policy: {json.dumps(policy, default=str)}")
    return policy
