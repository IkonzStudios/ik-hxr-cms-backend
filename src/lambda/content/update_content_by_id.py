import json
import os
from typing import Dict, Any
from utils.helpers import (
    parse_request_body,
    get_content_by_id_from_db,
    prepare_update_data,
    update_content_in_db,
    create_content_response,
    create_error_response,
)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to update a content by ID in DynamoDB.

    Expected event structure:
    {
        "pathParameters": {
            "id": "content-uuid"
        },
        "body": {
            "url": "https://example.com/updated-video.mp4",
            "thumbnail": "https://example.com/updated-thumbnail.jpg",
            "title": "Updated Video Content",
            "description": "Updated description",
            "is_active": false,
            "is_deleted": false,
            "assigned_to": "[\"device-id-3\", \"device-id-4\"]",
            "playlists": "[\"playlist-id-3\"]",
            "updated_by": "user-id-456"
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

        # Parse request body
        body, parse_error = parse_request_body(event)
        if parse_error:
            return parse_error

        # Check if body has any updateable fields
        if not body:
            return create_error_response(400, "Request body cannot be empty")

        # Prepare update data
        update_data = prepare_update_data(body)

        if not update_data:
            return create_error_response(400, "No valid fields to update")

        # Update content in database
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
        print(f"Error updating content: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback

        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, "Internal server error")
