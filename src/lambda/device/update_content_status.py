import json
import os
import traceback
from typing import Dict, Any
import boto3

from utils.helpers import (
    parse_request_body,
    create_error_response,
    get_cors_headers,
    get_device_by_id_from_db,
    update_device_in_db,
)
from utils.rbac import check_edit_permission_with_org

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to update content status on a device.

    Expected event structure:
    {
        "pathParameters": {
            "id": "device-uuid"
        },
        "body": {
            "content_id": "content-uuid",
            "status": "initiated|downloading|downloaded|failed"
        },
        "requestContext": {
            "authorizer": {
                "user_id": "user-sub",
                "email": "user@example.com",
                "role": "admin",
                "organization_id": "org-123"
            }
        }
    }
    """

    try:
        # Get table names from environment variables
        devices_table_name = os.environ.get("DEVICES_TABLE_NAME")
        contents_table_name = os.environ.get("CONTENTS_TABLE_NAME")
        
        if not devices_table_name:
            raise ValueError("DEVICES_TABLE_NAME environment variable not set")
        if not contents_table_name:
            raise ValueError("CONTENTS_TABLE_NAME environment variable not set")

        # Debug: Print the event structure
        print(f"Event: {json.dumps(event)}")

        # Parse request body
        body, parse_error = parse_request_body(event)
        if parse_error:
            return parse_error

        # Extract device ID from path parameters
        path_parameters = event.get("pathParameters", {})
        device_id = path_parameters.get("id") if path_parameters else None

        if not device_id:
            return create_error_response(400, "Device ID is required")

        # Validate required fields in request body
        content_id = body.get("content_id")
        status = body.get("status")

        if not content_id:
            return create_error_response(400, "content_id is required")
        if not status:
            return create_error_response(400, "status is required")

        # Validate status value
        valid_statuses = ["initiated", "downloading", "downloaded", "failed"]
        if status not in valid_statuses:
            return create_error_response(400, f"status must be one of: {', '.join(valid_statuses)}")

        # Get the device to check its organization_id and current content status
        device, get_error = get_device_by_id_from_db(device_id, devices_table_name)
        if get_error:
            return get_error

        # RBAC: Check if user has permission to update devices in this organization
        rbac_error, user_info = check_edit_permission_with_org(event, "device", device["organization_id"])
        if rbac_error:
            return rbac_error

        # Log user action for audit
        print(f"User {user_info['user_id']} ({user_info['role']}) updating content status for device {device_id}")

        # Validate that content exists
        try:
            dynamodb = boto3.resource("dynamodb")
            contents_table = dynamodb.Table(contents_table_name)
            
            content_response = contents_table.get_item(Key={"id": content_id})
            if "Item" not in content_response:
                return create_error_response(404, "Content not found")
        except Exception as e:
            print(f"Error validating content: {str(e)}")
            return create_error_response(500, "Error validating content")

        # Get current content arrays
        contents_initiated = device.get("contents_initiated", [])
        contents_downloading = device.get("contents_downloading", [])
        contents_downloaded = device.get("contents_downloaded", [])

        print(f"Contents initiated: {contents_initiated}")
        print(f"Contents downloading: {contents_downloading}")
        print(f"Contents downloaded: {contents_downloaded}")

        # Convert string arrays to lists if needed
        if isinstance(contents_initiated, str):
            contents_initiated = json.loads(contents_initiated) if contents_initiated else []
        if isinstance(contents_downloading, str):
            contents_downloading = json.loads(contents_downloading) if contents_downloading else []
        if isinstance(contents_downloaded, str):
            contents_downloaded = json.loads(contents_downloaded) if contents_downloaded else []

        # Remove content_id from all arrays first
        # if content_id in contents_initiated:
        #     contents_initiated.remove(content_id)
        # if content_id in contents_downloading:
        #     contents_downloading.remove(content_id)
        # if content_id in contents_downloaded:
        #     contents_downloaded.remove(content_id)

        # Add content_id to the appropriate array based on status
        if status == "initiated":
            if content_id not in contents_initiated:
                contents_initiated.append(content_id)
        elif status == "downloading":
            # Validate that content was previously initiated
            if content_id not in contents_initiated:
                return create_error_response(400, "Content must be in 'initiated' status before moving to 'downloading'")
            if content_id not in contents_downloading:
                contents_downloading.append(content_id)
                if content_id in contents_initiated:
                    contents_initiated.remove(content_id)
        elif status == "downloaded":
            # Validate that content was previously downloading
            if content_id not in contents_downloading:
                return create_error_response(400, "Content must be in 'downloading' status before moving to 'downloaded'")
            if content_id not in contents_downloaded:
                contents_downloaded.append(content_id)
                if content_id in contents_downloading:
                    contents_downloading.remove(content_id)
        elif status == "failed":
            # For failed status, we don't add to any array (content is removed from all status arrays)
            if content_id in contents_initiated:
                contents_initiated.remove(content_id)
            if content_id in contents_downloading:
                contents_downloading.remove(content_id)
            if content_id in contents_downloaded:
                contents_downloaded.remove(content_id)
            # TODO: add content to failed array

        # Prepare update data
        update_data = {
            "contents_initiated": contents_initiated,
            "contents_downloading": contents_downloading,
            "contents_downloaded": contents_downloaded,
        }

        # Update device in database
        update_error = update_device_in_db(device_id, update_data, devices_table_name)
        if update_error:
            return update_error

        # Return success response
        return {
            "statusCode": 200,
            "headers": get_cors_headers(),
            "body": json.dumps({
                "message": f"Content status updated successfully to '{status}'",
                "device_id": device_id,
                "content_id": content_id,
                "status": status,
                "updated_status_arrays": {
                    "contents_initiated": contents_initiated,
                    "contents_downloading": contents_downloading,
                    "contents_downloaded": contents_downloaded,
                }
            }),
        }

    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        print(f"Error updating content status: {str(e)}")
        print(f"Error type: {type(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, "Internal server error")
