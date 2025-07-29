import json
import os
import boto3
import jwt
import requests
from typing import Dict, Any
from botocore.exceptions import ClientError
from jwt import PyJWK
import time


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
        region = os.environ.get("AWS_REGION", "us-east-2")

        print(f"User Pool ID: {user_pool_id}")
        print(f"Client ID: {user_pool_client_id}")
        print(f"Region: {region}")

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

        # Verify and decode JWT token using PyJWT
        try:
            # Get Cognito public keys
            jwks_url = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json"
            print(f"Fetching JWKS from: {jwks_url}")
            
            jwks_response = requests.get(jwks_url, timeout=10)
            jwks_response.raise_for_status()
            jwks = jwks_response.json()
            
            # Decode token header to get the key ID
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")
            
            if not kid:
                print("ERROR: No 'kid' found in token header")
                return generate_policy("user", "Deny", event["methodArn"])
            
            print(f"Token kid: {kid}")
            
            # Find the correct key
            signing_key = None
            for key in jwks["keys"]:
                if key["kid"] == kid:
                    # Create PyJWK object and get the key
                    jwk = PyJWK.from_dict(key)
                    signing_key = jwk.key
                    break
            
            if not signing_key:
                print(f"ERROR: Public key not found for kid: {kid}")
                return generate_policy("user", "Deny", event["methodArn"])
            
            print("Public key found and converted")
            
            # Verify and decode the token
            decoded_token = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                audience=user_pool_client_id,
                issuer=f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"
            )
            
            print(f"Token successfully verified and decoded")
            print(f"Decoded token payload: {json.dumps(decoded_token, default=str)}")

            # Extract user information
            user_id = decoded_token.get("sub")
            email = decoded_token.get("email")
            role = decoded_token.get("custom:role", "user")
            organization_id = decoded_token.get("custom:organization_id", "")
            
            # Verify token expiration
            exp = decoded_token.get("exp")
            if exp and exp < time.time():
                print("ERROR: Token has expired")
                return generate_policy("user", "Deny", event["methodArn"])

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

        except jwt.ExpiredSignatureError:
            print("ERROR: Token has expired")
            return generate_policy("user", "Deny", event["methodArn"])
        except jwt.InvalidTokenError as e:
            print(f"ERROR: Invalid token - {str(e)}")
            return generate_policy("user", "Deny", event["methodArn"])
        except requests.RequestException as e:
            print(f"ERROR: Failed to fetch JWKS - {str(e)}")
            return generate_policy("user", "Deny", event["methodArn"])
        except Exception as e:
            print(f"Token verification error: {str(e)}")
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
                    # "Resource": resource,
                    "Resource": "arn:aws:execute-api:us-east-2:217968404084:wztl4nwcy5/*/*"
                }
            ],
        },
    }

    if context:
        policy["context"] = context

    print(f"Generated policy: {json.dumps(policy, default=str)}")
    return policy
