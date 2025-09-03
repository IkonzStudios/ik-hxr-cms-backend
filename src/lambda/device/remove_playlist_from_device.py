import json
import os
import traceback
import boto3
from typing import Dict, Any

from utils.helpers import (
    parse_request_body,
    get_device_by_id_from_db,
    create_device_response,
    create_error_response,
    update_device_in_db,
)
from iot.remove_content import remove_content_from_device_utility
from utils.rbac import check_edit_permission_with_org
from utils.constants import HTTP_STATUS_CODES, DEVICE_ERROR_MESSAGES, DEVICE_SUCCESS_MESSAGES


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to remove playlist from a device.

    Expected event structure:
    {
        "pathParameters": {
            "id": "device-uuid"
        },
        "body": {
            "playlist_ids": ["playlist1", "playlist2"]
        }
    }
    """

    try:
        # Get table name from environment variable
        table_name = os.environ.get("DEVICES_TABLE_NAME")
        if not table_name:
            return create_error_response(500, DEVICE_ERROR_MESSAGES["MISSING_ENVIRONMENT_VAR"])

        # Debug: Print the event structure
        print(f"Event: {json.dumps(event)}")

        # Extract device ID from path parameters
        path_parameters = event.get("pathParameters", {})
        device_id = path_parameters.get("id") if path_parameters else None

        if not device_id:
            return create_error_response(400, DEVICE_ERROR_MESSAGES["DEVICE_ID_REQUIRED"])

        # First get the existing device to check its organization_id for RBAC
        existing_device, get_error = get_device_by_id_from_db(device_id, table_name)
        if get_error:
            return get_error

        # RBAC: Check if user has permission to edit devices in this organization
        rbac_error, user_info = check_edit_permission_with_org(event, "device", existing_device["organization_id"])
        if rbac_error:
            return rbac_error

        # Log user action for audit
        print(f"User {user_info['user_id']} ({user_info['role']}) removing playlist from device {device_id}")

        # Parse request body
        body, parse_error = parse_request_body(event)
        if parse_error:
            return parse_error

        # Check if body has playlist_ids
        if not body:
            return create_error_response(400, DEVICE_ERROR_MESSAGES["EMPTY_REQUEST_BODY"])

        playlist_ids = body.get("playlist_ids")
        if not playlist_ids:
            return create_error_response(400, DEVICE_ERROR_MESSAGES["INVALID_PLAYLIST_IDS"])

        if not isinstance(playlist_ids, list):
            return create_error_response(400, DEVICE_ERROR_MESSAGES["INVALID_PLAYLIST_IDS"])

        # Validate playlist IDs are strings
        for playlist_id in playlist_ids:
            if not isinstance(playlist_id, str) or not playlist_id.strip():
                return create_error_response(400, DEVICE_ERROR_MESSAGES["INVALID_PLAYLIST_IDS"])

        # Store original device state for rollback
        original_playlists = existing_device.get("playlists", [])
        if isinstance(original_playlists, str):
            original_playlists = json.loads(original_playlists) if original_playlists else []

        # Get environment variables for IoT API call
        contents_table_name = os.environ.get("CONTENTS_TABLE_NAME")
        content_bucket_name = os.environ.get("CONTENT_BUCKET_NAME")
        playlists_table_name = os.environ.get("PLAYLISTS_TABLE_NAME")
        
        if not contents_table_name:
            return create_error_response(500, "CONTENTS_TABLE_NAME environment variable not set")
        if not content_bucket_name:
            return create_error_response(500, "CONTENT_BUCKET_NAME environment variable not set")
        if not playlists_table_name:
            return create_error_response(500, "PLAYLISTS_TABLE_NAME environment variable not set")
        
        # Get content IDs from playlists being removed
        dynamodb = boto3.resource("dynamodb")
        playlists_table = dynamodb.Table(playlists_table_name)
        contents_table = dynamodb.Table(contents_table_name)
        
        content_ids_to_remove = []
        for playlist_id in playlist_ids:
            try:
                response = playlists_table.get_item(Key={"id": playlist_id})
                if "Item" in response:
                    playlist_item = response["Item"]
                    playlist_contents = playlist_item.get("contents", [])
                    if isinstance(playlist_contents, str):
                        playlist_contents = json.loads(playlist_contents) if playlist_contents else []
                    content_ids_to_remove.extend(playlist_contents)
            except Exception as e:
                print(f"Error retrieving playlist {playlist_id}: {str(e)}")
                continue
        
        # Remove duplicates
        content_ids_to_remove = list(set(content_ids_to_remove))
        
        # Call IoT API to remove content from device if there are contents to remove
        if content_ids_to_remove:
            success, error_msg, iot_response = remove_content_from_device_utility(
                device_id=device_id,
                content_ids=content_ids_to_remove,
                contents_table_name=contents_table_name,
                content_bucket_name=content_bucket_name,
                devices_table_name=table_name
            )
            
            if not success:
                return create_error_response(502, f"IoT API error: {error_msg}")
        else:
            iot_response = None
        
        database_updated = False
        
        try:
            # Update device's playlist list in database by removing specified playlist IDs
            current_playlists = existing_device.get("playlists", [])
            if isinstance(current_playlists, str):
                current_playlists = json.loads(current_playlists) if current_playlists else []
            
            # Check if playlist IDs exist in current playlists
            playlist_ids_to_remove = [pid for pid in playlist_ids if pid in current_playlists]
            if not playlist_ids_to_remove:
                return create_error_response(400, "None of the specified playlist IDs are currently assigned to this device")
            
            # Remove specified playlist IDs from existing ones
            updated_playlists = [playlist for playlist in current_playlists if playlist not in playlist_ids]
            update_data = {"playlists": updated_playlists}
            
            update_error = update_device_in_db(device_id, update_data, table_name)
            if update_error:
                return update_error
            
            database_updated = True
                
            # Get updated device to return in response
            updated_device, get_error = get_device_by_id_from_db(device_id, table_name)
            if get_error:
                updated_device = existing_device  # Fallback to existing device
            
            # Create success result for response
            playlist_removal_result = {
                "success": True,
                "message": DEVICE_SUCCESS_MESSAGES['PLAYLIST_REMOVED'],
                "removed_playlist_ids": playlist_ids_to_remove,
                "remaining_playlists": len(updated_playlists),
                "content_removal": {
                    "content_ids_removed": content_ids_to_remove,
                    "iot_response": iot_response
                } if content_ids_to_remove else None
            }
            
            print(f"Playlist removal successful for device {device_id}")
            if content_ids_to_remove:
                print(f"Content removal via IoT API successful: {len(content_ids_to_remove)} content items removed")
                print(f"IoT API response: {json.dumps(iot_response, indent=2)}")
            else:
                print("No content items to remove from device")
            
            return create_device_response(updated_device, {"playlist_removal": playlist_removal_result})
                
        except Exception as e:
            print(f"Error during playlist removal: {str(e)}")
            
            # Rollback database changes if they were made
            if database_updated:
                try:
                    print("Rolling back database changes due to error")
                    rollback_data = {"playlists": original_playlists}
                    update_device_in_db(device_id, rollback_data, table_name)
                    print("Database rollback successful")
                except Exception as rollback_error:
                    print(f"Database rollback failed: {str(rollback_error)}")
            
            return create_error_response(500, f"Playlist removal failed: {str(e)}")

    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        print(f"Error removing playlist from device: {str(e)}")
        print(f"Error type: {type(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, HTTP_STATUS_CODES[500])
