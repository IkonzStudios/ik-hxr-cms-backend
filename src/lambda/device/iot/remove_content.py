"""
IoT content removal utilities for device management.
"""

import json
import os
import requests
import uuid
import time
import traceback
from typing import Dict, Any, List, Tuple, Optional
import boto3

from utils.constants import IOT_API_URL


def remove_content_from_device_utility(
    device_id: str, 
    content_ids: List[str], 
    contents_table_name: str,
    content_bucket_name: str,
    devices_table_name: str = None
) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Utility function to remove content from a device by calling external IoT API.
    This function looks up content details from DynamoDB and calls the delete content API.
    
    Args:
        device_id: The device ID to remove content from
        content_ids: List of content IDs from the CMS database
        contents_table_name: DynamoDB table name for contents
        content_bucket_name: S3 bucket name for content storage
        devices_table_name: DynamoDB table name for devices (optional)
        
    Returns:
        Tuple of (success, error_message, iot_response)
    """
    try:
        # Get environment variables
        if not devices_table_name:
            devices_table_name = os.environ.get("DEVICES_TABLE_NAME")
        iot_delete_api_url = os.environ.get("IOT_DELETE_CONTENT_API_URL", IOT_API_URL + "/ct-delete")
        
        if not devices_table_name:
            return False, "DEVICES_TABLE_NAME environment variable not set", None

        # Validate inputs
        if not device_id or not isinstance(device_id, str):
            return False, "device_id must be a non-empty string", None
        
        if not content_ids or not isinstance(content_ids, list):
            return False, "content_ids must be a non-empty list", None

        # Check if device exists in our database
        dynamodb = boto3.resource("dynamodb")
        devices_table = dynamodb.Table(devices_table_name)
        
        response = devices_table.get_item(Key={"id": device_id})
        if "Item" not in response:
            return False, "Device not found", None

        # Look up content details from DynamoDB
        contents_table = dynamodb.Table(contents_table_name)
        
        content_list = []
        for content_id in content_ids:
            try:
                response = contents_table.get_item(Key={"id": content_id})
                if "Item" in response:
                    content_item = response["Item"]
                    # Build S3 key from content metadata
                    s3_key = content_item.get("url")
                    if s3_key:
                        content_list.append({
                            "s3_bucket": content_bucket_name,
                            "s3_key": s3_key
                        })
                    else:
                        print(f"Warning: No S3 key found for content {content_id}")
                else:
                    print(f"Warning: Content {content_id} not found in database")
            except Exception as e:
                print(f"Error retrieving content {content_id}: {str(e)}")
                continue

        if not content_list:
            return False, "No valid content files found for removal", None

        # Generate unique deletion ID
        deletion_id = f"cl-{int(time.time() * 1000)}"

        # Transform contents to match IoT API format
        iot_contents = []
        for content in content_list:
            iot_contents.append({
                "s3Bucket": content["s3_bucket"],
                "s3Key": content["s3_key"]
            })

        # Prepare payload for external IoT API
        iot_payload = {
            "action": "delete_content",
            "thingName": device_id,
            "payload": {
                "deletionId": deletion_id,
                "contents": iot_contents
            }
        }

        print(f"Removing content from device {device_id}")
        print(f"IoT API Payload: {json.dumps(iot_payload, indent=2)}")

        # Call external IoT API
        response = requests.post(
            iot_delete_api_url,
            json=iot_payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        print(f"IoT API Response Status: {response.status_code}")
        print(f"IoT API Response: {response.text}")

        if response.status_code == 200:
            # Parse the IoT API response
            iot_response = response.json() if response.text else {}
            return True, None, iot_response
        else:
            return False, f"IoT API returned status {response.status_code}: {response.text}", None

    except requests.exceptions.RequestException as e:
        error_msg = f"Failed to communicate with IoT API: {str(e)}"
        print(error_msg)
        return False, error_msg, None
    except Exception as e:
        error_msg = f"Error removing content from device: {str(e)}"
        print(error_msg)
        print(f"Traceback: {traceback.format_exc()}")
        return False, error_msg, None
