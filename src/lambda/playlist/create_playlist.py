import json
import os
from typing import Dict, Any
from utils.helpers import (
    parse_request_body,
    validate_required_fields,
    create_playlist_data,
    save_playlist_to_db,
    create_success_response,
    create_error_response,
)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to create a new playlist in DynamoDB.

    Expected event structure:
    {
        "name": "Marketing Campaign 2024",
        "description": "Collection of marketing videos for Q4 campaign",
        "contents": "[\"content-id-1\", \"content-id-2\", \"content-id-3\"]",
        "organization_id": "123e4567-e89b-12d3-a456-426614174000",
        "created_by": "user-id-123",
        "updated_by": "user-id-123"
    }
    """

    try:
        # Get table name from environment variable
        table_name = os.environ.get("PLAYLISTS_TABLE_NAME")
        if not table_name:
            raise ValueError("PLAYLISTS_TABLE_NAME environment variable not set")

        # Debug: Print the event structure
        print(f"Event: {json.dumps(event)}")

        # Parse request body
        body, parse_error = parse_request_body(event)
        if parse_error:
            return parse_error

        # Validate required fields
        validation_error = validate_required_fields(body)
        if validation_error:
            return validation_error

        # Create playlist data
        playlist_data = create_playlist_data(body)

        # Save to database
        save_error = save_playlist_to_db(playlist_data, table_name)
        if save_error:
            return save_error

        # Return success response
        return create_success_response(playlist_data)

    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        print(f"Error creating playlist: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback

        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, "Internal server error")
