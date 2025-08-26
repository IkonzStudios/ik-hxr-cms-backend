import json
import os
import sys
from typing import Dict, Any

from utils.helpers import (
    parse_request_body,
    validate_required_fields,
    validate_content_fields,
    create_content_data,
    save_content_to_db,
    create_success_response,
    create_error_response,
)
from utils.rbac import check_upload_permission_with_org


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to create a new content in DynamoDB.

    Expected event structure:
    {
        "url": "https://example.com/video.mp4",
        "thumbnail": "https://example.com/thumbnail.jpg",
        "title": "Sample Video Content",
        "description": "This is a sample video for testing",
        "size": "1048576",
        "duration": "120.5",
        "type": "video/mp4",
        "status": "PENDING",  // Optional: PENDING, REJECTED, APPROVED (defaults to PENDING)
        "is_deleted": false,
        "assigned_to": "[\"device-id-1\", \"device-id-2\"]",
        "organization_id": "123e4567-e89b-12d3-a456-426614174000",
        "created_by": "user-id-123",
        "updated_by": "user-id-123"
    }
    """

    try:
        # Get table name from environment variable
        table_name = os.environ.get("CONTENTS_TABLE_NAME")
        if not table_name:
            raise ValueError("CONTENTS_TABLE_NAME environment variable not set")

        # Debug: Print the event structure
        print(f"Event: {json.dumps(event)}")

        # Parse request body first to get organization_id for RBAC check
        body, parse_error = parse_request_body(event)
        if parse_error:
            return parse_error

        # Extract organization_id from request body for RBAC validation
        organization_id = body.get("organization_id", "")
        if not organization_id:
            return create_error_response(400, "organization_id is required")

        # RBAC: Check if user has permission to upload content in this organization
        rbac_error, user_info = check_upload_permission_with_org(event, "content", organization_id)
        if rbac_error:
            return rbac_error

        # Log user action for audit
        print(f"User {user_info['user_id']} ({user_info['role']}) creating content in org {organization_id}")

        # Validate required fields
        validation_error = validate_required_fields(body)
        if validation_error:
            return validation_error

        # Validate content fields
        field_validation_error = validate_content_fields(body)
        if field_validation_error:
            return create_error_response(400, field_validation_error)

        # Create content data
        content_data = create_content_data(body)

        # Save to database
        save_error = save_content_to_db(content_data, table_name)
        if save_error:
            return save_error

        # Return success response
        return create_success_response(content_data)

    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        print(f"Error creating content: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback

        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, "Internal server error")
