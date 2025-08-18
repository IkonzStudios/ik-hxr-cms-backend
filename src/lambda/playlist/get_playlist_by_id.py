import json
import os
from typing import Dict, Any
from utils.helpers import (
    get_playlist_by_id_from_db,
    create_playlist_response,
    create_error_response,
)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to get a playlist by ID from DynamoDB.

    Expected event structure:
    {
        "pathParameters": {
            "id": "playlist-uuid"
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

        # Get playlist from database
        playlist, get_error = get_playlist_by_id_from_db(playlist_id, table_name)
        if get_error:
            return get_error

        # Return success response
        return create_playlist_response(playlist)

    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        print(f"Error getting playlist: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback

        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, "Internal server error")
