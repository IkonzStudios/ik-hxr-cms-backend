import json
import os
from typing import Dict, Any
from utils.helpers import (
    get_playbacks_by_org_id_from_db,
    create_playbacks_list_response,
    create_error_response,
)
from utils.rbac import check_view_permission


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for getting all playbacks by organization ID.

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

        # Get organization ID from path parameters
        org_id = event.get("pathParameters", {}).get("orgId")
        if not org_id:
            return create_error_response(400, "Organization ID is required")

        # Get table name from environment
        table_name = os.environ.get("PLAYBACKS_TABLE_NAME")
        contents_table_name = os.environ.get("CONTENTS_TABLE_NAME")
        schedules_table_name = os.environ.get("SCHEDULES_TABLE_NAME")
        if not table_name:
            return create_error_response(500, "Table name not configured")
        if not contents_table_name:
            return create_error_response(500, "Contents table name not configured")
        if not schedules_table_name:
            return create_error_response(500, "Schedules table name not configured")

        # Get playbacks by organization ID
        playbacks, error_response = get_playbacks_by_org_id_from_db(org_id, table_name, contents_table_name, schedules_table_name)
        if error_response:
            return error_response

        # Return success response
        return create_playbacks_list_response(playbacks)

    except Exception as e:
        print(f"Unexpected error in get_all_playbacks_by_org_id: {str(e)}")
        return create_error_response(500, "Internal server error")
