import json
import os
from typing import Dict, Any
from utils.helpers import (
    get_playback_by_id_from_db,
    create_playback_response,
    create_error_response,
)
from utils.rbac import check_view_permission


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for getting a playback by ID.

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        API Gateway response
    """
    try:
        # Handle CORS preflight request
        if event.get("httpMethod") == "OPTIONS":
            return {
                "statusCode": 200,
                "headers": {
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token,X-Requested-With,Origin,Accept,Cache-Control,Pragma,If-Modified-Since,X-Forwarded-For,X-Forwarded-Proto,X-Forwarded-Port",
                    "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS,PATCH,HEAD",
                    "Access-Control-Max-Age": "86400",
                },
                "body": "",
            }

        # Check RBAC permissions
        rbac_error, user_info = check_view_permission(event, "playback")
        if rbac_error:
            return rbac_error

        # Get playback ID from path parameters
        playback_id = event.get("pathParameters", {}).get("id")
        if not playback_id:
            return create_error_response(400, "Playback ID is required")

        # Get table name from environment
        table_name = os.environ.get("PLAYBACKS_TABLE_NAME")
        if not table_name:
            return create_error_response(500, "Table name not configured")

        # Get playback by ID
        playback_data, error_response = get_playback_by_id_from_db(playback_id, table_name)
        if error_response:
            return error_response

        # Return success response
        return create_playback_response(playback_data)

    except Exception as e:
        print(f"Unexpected error in get_playback_by_id: {str(e)}")
        return create_error_response(500, "Internal server error")
