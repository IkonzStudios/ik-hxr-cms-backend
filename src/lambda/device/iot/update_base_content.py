"""
IoT base content update utilities for device management.
"""

import json
import os
import requests
import traceback
from typing import Dict, Any, Tuple, Optional
import boto3

from utils.helpers import get_iot_url_for_device


def update_device_base_content_utility(
    device_id: str, 
    base_content_s3_key: str,
    content_bucket_name: str,
    devices_table_name: str = None
) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Utility function to update base content for a device by calling external IoT API.
    This function calls the IoT API to update the default loop content for the device.
    
    Args:
        device_id: The device ID to update base content for
        base_content_s3_key: The S3 key for the base content (e.g., "base-contents/org-id/uuid.mp4")
        content_bucket_name: S3 bucket name for content storage
        devices_table_name: DynamoDB table name for devices (optional)
        
    Returns:
        Tuple of (success, error_message, iot_response)
    """
    try:
        # Get environment variables
        if not devices_table_name:
            devices_table_name = os.environ.get("DEVICES_TABLE_NAME")

        if not devices_table_name:
            return False, "DEVICES_TABLE_NAME environment variable not set", None

        # Validate inputs
        if not device_id or not isinstance(device_id, str):
            return False, "device_id must be a non-empty string", None
        
        if not base_content_s3_key or not isinstance(base_content_s3_key, str):
            return False, "base_content_s3_key must be a non-empty string", None

        if not content_bucket_name or not isinstance(content_bucket_name, str):
            return False, "content_bucket_name must be a non-empty string", None

        # Check if device exists in our database
        dynamodb = boto3.resource("dynamodb")
        devices_table = dynamodb.Table(devices_table_name)

        response = devices_table.get_item(Key={"id": device_id})
        if "Item" not in response:
            return False, "Device not found", None

        device_item = response["Item"]
        iot_update_api_url = get_iot_url_for_device(
            device_item, "IOT_UPDATE_API_URL", "IOT_UPDATE_API_URL_OLD"
        )
        if not iot_update_api_url:
            return False, "IOT_UPDATE_API_URL environment variable not set", None

        # Prepare payload for external IoT API
        iot_payload = {
            "action": "update_default_loop",
            "thingName": device_id,
            "payload": {
                "s3Bucket": content_bucket_name,
                "s3Key": base_content_s3_key
            }
        }

        print(f"Updating base content for device {device_id}")
        print(f"IoT API Payload: {json.dumps(iot_payload, indent=2)}")

        # Call external IoT API
        response = requests.post(
            iot_update_api_url,
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
        error_msg = f"Error updating base content for device: {str(e)}"
        print(error_msg)
        print(f"Traceback: {traceback.format_exc()}")
        return False, error_msg, None
