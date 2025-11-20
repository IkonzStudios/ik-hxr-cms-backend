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
from utils.rbac import check_edit_permission_with_org
from utils.constants import HTTP_STATUS_CODES, DEVICE_ERROR_MESSAGES, DEVICE_SUCCESS_MESSAGES
from iot.assign_content import assign_content_to_device_utility


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to assign playlist to a device.

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
        print(f"User {user_info['user_id']} ({user_info['role']}) assigning playlist to device {device_id}")

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
        
        original_contents_initiated = existing_device.get("contents_initiated", [])
        if isinstance(original_contents_initiated, str):
            original_contents_initiated = json.loads(original_contents_initiated) if original_contents_initiated else []

        # Trigger IoT playlist assignment via content assignment
        iot_assignment_result = None
        database_updated = False
        
        try:
            # First, get contents from playlists and call IoT API
            
            # Get required environment variables
            playlists_table_name = os.environ.get("PLAYLISTS_TABLE_NAME")
            contents_table_name = os.environ.get("CONTENTS_TABLE_NAME")
            content_bucket_name = os.environ.get("CONTENT_BUCKET_NAME")
            
            if not (playlists_table_name and contents_table_name and content_bucket_name):
                return create_error_response(500, DEVICE_ERROR_MESSAGES["MISSING_ENVIRONMENT_VAR"])

            print(f"Triggering IoT playlist assignment for device {device_id}")
            
            # Get all contents from all playlists
            dynamodb = boto3.resource("dynamodb")
            playlists_table = dynamodb.Table(playlists_table_name)
            all_content_ids = []
            
            for playlist_id in playlist_ids:
                try:
                    response = playlists_table.get_item(Key={"id": playlist_id})
                    if "Item" in response:
                        playlist_item = response["Item"]
                        playlist_contents = playlist_item.get("contents", [])
                        if isinstance(playlist_contents, str):
                            playlist_contents = json.loads(playlist_contents) if playlist_contents else []
                        all_content_ids.extend(playlist_contents)
                    else:
                        print(f"Warning: Playlist {playlist_id} not found in database")
                except Exception as e:
                    print(f"Error retrieving playlist {playlist_id}: {str(e)}")
                    continue
            
            # Remove duplicates
            all_content_ids = list(set(all_content_ids))
            
            if not all_content_ids:
                print("Warning: No content found in playlists")
                # Still proceed with database update even if no content
            else:
                # Call IoT API with content IDs from playlists
                success, error_msg, iot_response = assign_content_to_device_utility(
                    device_id=device_id,
                    content_ids=all_content_ids,
                    contents_table_name=contents_table_name,
                    content_bucket_name=content_bucket_name,
                    devices_table_name=table_name
                )
                
                iot_assignment_result = {
                    "success": success,
                    "error": error_msg,
                    "response": iot_response,
                    "content_ids_from_playlists": all_content_ids
                }
                
                if not success:
                    print(f"IoT playlist assignment failed for device {device_id}: {error_msg}")
                    return create_error_response(502, f"{DEVICE_ERROR_MESSAGES['ASSIGNMENT_FAILED']}: {error_msg}")
                
                print(f"IoT playlist assignment successful for device {device_id}")

            # Update device's playlist list in database
            current_playlists = existing_device.get("playlists", [])
            if isinstance(current_playlists, str):
                current_playlists = json.loads(current_playlists) if current_playlists else []
            
            # Add new playlist IDs to existing ones (avoid duplicates)
            updated_playlists = list(set(current_playlists + playlist_ids))
            update_data = {"playlists": updated_playlists}
            
            # Update contents_initiated with content IDs that are not already in any content status list
            if all_content_ids:
                # Get current content status lists
                current_contents_initiated = existing_device.get("contents_initiated", [])
                if isinstance(current_contents_initiated, str):
                    current_contents_initiated = json.loads(current_contents_initiated) if current_contents_initiated else []
                
                current_contents_downloading = existing_device.get("contents_downloading", [])
                if isinstance(current_contents_downloading, str):
                    current_contents_downloading = json.loads(current_contents_downloading) if current_contents_downloading else []
                
                current_contents_downloaded = existing_device.get("contents_downloaded", [])
                if isinstance(current_contents_downloaded, str):
                    current_contents_downloaded = json.loads(current_contents_downloaded) if current_contents_downloaded else []
                
                # Combine all existing content IDs from the three status lists
                existing_content_ids = set(current_contents_initiated + current_contents_downloading + current_contents_downloaded)
                
                # Find content IDs that are not in any of the status lists
                new_content_ids = [content_id for content_id in all_content_ids if content_id not in existing_content_ids]
                
                # Add new content IDs to contents_initiated
                if new_content_ids:
                    updated_contents_initiated = current_contents_initiated.copy()
                    for content_id in new_content_ids:
                        if content_id not in updated_contents_initiated:
                            updated_contents_initiated.append(content_id)
                    update_data["contents_initiated"] = updated_contents_initiated
            
            update_error = update_device_in_db(device_id, update_data, table_name)
            if update_error:
                print(f"Database update failed after successful IoT assignment: {update_error}")
                # TODO: Implement IoT rollback when rollback API becomes available
                return update_error
            
            database_updated = True
                
            # Get updated device to return in response
            updated_device, get_error = get_device_by_id_from_db(device_id, table_name)
            if get_error:
                updated_device = existing_device  # Fallback to existing device
            
            # Create success result for response
            playlist_assignment_result = {
                "success": True,
                "message": DEVICE_SUCCESS_MESSAGES["PLAYLIST_ASSIGNED"],
                "assigned_playlist_ids": playlist_ids,
                "total_playlists": len(updated_playlists),
                "content_ids_assigned": all_content_ids
            }
            
            # Combine results
            if iot_assignment_result:
                playlist_assignment_result["iot_assignment"] = iot_assignment_result
            
            print(f"Playlist assignment successful for device {device_id}")
            return create_device_response(updated_device, {"playlist_assignment": playlist_assignment_result})
                
        except Exception as e:
            print(f"Error during playlist assignment: {str(e)}")
            
            # Rollback database changes if they were made
            if database_updated:
                try:
                    print("Rolling back database changes due to error")
                    rollback_data = {
                        "playlists": original_playlists,
                        "contents_initiated": original_contents_initiated
                    }
                    update_device_in_db(device_id, rollback_data, table_name)
                    print("Database rollback successful")
                except Exception as rollback_error:
                    print(f"Database rollback failed: {str(rollback_error)}")
            
            return create_error_response(500, f"{DEVICE_ERROR_MESSAGES['ASSIGNMENT_FAILED']}: {str(e)}")

    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        print(f"Error assigning playlist to device: {str(e)}")
        print(f"Error type: {type(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, HTTP_STATUS_CODES[500])
