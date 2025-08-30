import json
import os
from typing import Dict, Any

from utils.helpers import (
    parse_request_body,
    get_content_by_id_from_db,
    update_content_in_db,
    create_content_response,
    create_error_response,
)
from utils.rbac import check_edit_permission_with_org


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to update content status by ID in DynamoDB.
    Only allows status changes from PENDING to APPROVED or REJECTED.

    Expected event structure:
    {
        "pathParameters": {
            "id": "content-uuid"
        },
        "body": {
            "status": "APPROVED"  // Must be either "APPROVED" or "REJECTED"
        }
    }
    """

    try:
        # Get table name from environment variable
        table_name = os.environ.get("CONTENTS_TABLE_NAME")
        if not table_name:
            raise ValueError("CONTENTS_TABLE_NAME environment variable not set")

        # Debug: Print the event structure
        print(f"Event: {json.dumps(event)}")

        # Extract content ID from path parameters
        path_parameters = event.get("pathParameters", {})
        content_id = path_parameters.get("id") if path_parameters else None

        if not content_id:
            return create_error_response(400, "Content ID is required")

        # First get the existing content to check its organization_id for RBAC and current status
        existing_content, get_error = get_content_by_id_from_db(content_id, table_name)
        if get_error:
            return get_error

        # Check current content status
        current_status = existing_content.get("status", "PENDING")
        if current_status != "PENDING":
            return create_error_response(400, f"Cannot update content status. Current status is '{current_status}'. Only content with PENDING status can be updated.")

        # RBAC: Check if user has permission to edit content in this organization
        rbac_error, user_info = check_edit_permission_with_org(event, "content", existing_content["organization_id"])
        if rbac_error:
            return rbac_error

        # Log user action for audit
        print(f"User {user_info['user_id']} ({user_info['role']}) updating content status {content_id}")

        # Parse request body
        body, parse_error = parse_request_body(event)
        if parse_error:
            return parse_error

        # Check if body has status field
        if not body or "status" not in body:
            return create_error_response(400, "Request body must contain 'status' field")

        # Validate status value
        new_status = body["status"]
        if new_status not in ["APPROVED", "REJECTED"]:
            return create_error_response(400, "Status must be either 'APPROVED' or 'REJECTED'")

        # Prepare update data with only the status field
        update_data = {
            "status": new_status,
            "updated_by": user_info["user_id"]
        }

        # Update content status in database
        update_error = update_content_in_db(content_id, update_data, table_name)
        if update_error:
            return update_error

        # Get updated content to return in response
        updated_content, get_error = get_content_by_id_from_db(content_id, table_name)
        if get_error:
            return get_error

        # Return success response
        return create_content_response(updated_content)

    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        print(f"Error updating content status: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback

        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, "Internal server error")
