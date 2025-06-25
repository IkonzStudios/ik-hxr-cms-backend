import json
import os
from typing import Dict, Any
from utils.helpers import (
    parse_request_body,
    get_playlist_by_id_from_db,
    prepare_update_data,
    update_playlist_in_db,
    create_playlist_response,
    create_error_response,
)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to update a playlist by ID in DynamoDB.

    Expected event structure:
    {
        "pathParameters": {
            "id": "playlist-uuid"
        },
        "body": {
            "name": "Updated Marketing Campaign 2024",
            "description": "Updated collection of marketing videos",
            "contents": "[\"content-id-4\", \"content-id-5\", \"content-id-6\"]",
            "updated_by": "user-id-456"
        }
    }
    """

    try:
        # Get table name from environment variable
        table_name = os.environ.get("PLAYLISTS_TABLE_NAME")
        if not table_name:
            raise ValueError("PLAYLISTS_TABLE_NAME environment variable not set")

        # Debug: Print the event structure
        print(f"Event: {json.dumps(event)}")

        # Extract playlist ID from path parameters
        path_parameters = event.get("pathParameters", {})
        playlist_id = path_parameters.get("id") if path_parameters else None

        if not playlist_id:
            return create_error_response(400, "Playlist ID is required")

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

        # Update playlist in database
        update_error = update_playlist_in_db(playlist_id, update_data, table_name)
        if update_error:
            return update_error

        # Get updated playlist to return in response
        updated_playlist, get_error = get_playlist_by_id_from_db(playlist_id, table_name)
        if get_error:
            return get_error

        # Return success response
        return create_playlist_response(updated_playlist)

    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        print(f"Error updating playlist: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback

        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, "Internal server error")
