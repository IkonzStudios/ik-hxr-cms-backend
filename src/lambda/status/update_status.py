import json
import os
from typing import Dict, Any

from utils.helpers import (
    parse_request_body,
    create_error_response,
    get_cors_headers,
)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to update status for various entities (content, device, etc.).
    This is a general status update API that can handle different entity types.

    Expected event structure:
    {
        "body": {} // Empty object as assumption
        "requestContext": {
            "authorizer": {
                "user_id": "user-sub",
                "email": "user@example.com",
                "role": "admin",
                "organization_id": "org-123"
            }
        }
    }
    """

    try:
        # Debug: Print the event structure
        print(f"Event: {json.dumps(event)}")
        print(f"Event keys: {list(event.keys())}")
        print(f"Body key exists: {'body' in event}")
        print(f"Body value: {event.get('body')}")
        print(f"Body type: {type(event.get('body'))}")

        # Parse request body (assume empty object)
        body, parse_error = parse_request_body(event)
        if parse_error:
            return parse_error

        # For now, just print the received data and return success
        print(f"Status update request received:")
        print(f"  Request Body: {body}")
        print(f"  Event: {json.dumps(event, indent=2)}")

        # TODO: Implement actual status update logic
        # This would involve:
        # 1. Validating the entity exists
        # 2. Checking RBAC permissions
        # 3. Updating the appropriate table
        # 4. Handling entity-specific status validation

        # Return success response
        return {
            "statusCode": 200,
            "headers": get_cors_headers(),
            "body": json.dumps({
                "message": "Status update request received",
                "request_body": body,
                "note": "Status update logic not yet implemented - this is a placeholder response"
            }),
        }

    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        print(f"Error processing status update: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, "Internal server error")
