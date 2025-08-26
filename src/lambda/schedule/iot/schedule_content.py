"""
IoT content scheduling utilities for schedule management.
"""

import json
import os
import requests
import time
from typing import Dict, Any, List, Tuple, Optional
import boto3
from utils.helpers import collect_contents_from_playlists_and_contents

def call_iot_schedule_api(
    device_id: str, 
    schedule_time: str, 
    schedule_time_end: str, 
    playback_id: str, 
    contents: List[Dict[str, str]],
    iot_api_url: str
) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Call the external IoT scheduling API for a single device.
    
    Args:
        device_id: Device ID to schedule content for
        schedule_time: Start time in ISO format
        schedule_time_end: End time in ISO format
        playback_id: Unique schedule ID (used as scheduleId)
        contents: List of content dicts with s3Key only (per confluence spec)
        iot_api_url: IoT API endpoint URL
        
    Returns:
        Tuple of (success, error_message, response_data)
    """
    # Transform contents to match confluence specification (only s3Key needed)
    content_payload = {
        "contents": [{"s3Key": content["s3Key"]} for content in contents]
    }
    
    payload = {
        "action": "schedule_content",
        "thingName": device_id,
        "payload": {
            "scheduleId": str(playback_id),  # Use playback_id as scheduleId
            "scheduleType": "multimedia",
            "scheduleStartTime": schedule_time,
            "scheduleEndTime": schedule_time_end,
            "contentPayload": content_payload
        }
    }
    
    try:
        print(f"Calling IoT API for device {device_id}")
        print(f"Payload: {json.dumps(payload, indent=2)}")
        
        response = requests.post(
            iot_api_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        print(f"IoT API Response Status for device {device_id}: {response.status_code}")
        print(f"IoT API Response: {response.text}")
        
        if response.status_code == 200:
            response_data = response.json() if response.text else {}
            return True, None, response_data
        else:
            return False, f"IoT API returned status {response.status_code}: {response.text}", None
            
    except requests.exceptions.RequestException as e:
        error_msg = f"Failed to call IoT API for device {device_id}: {str(e)}"
        print(error_msg)
        return False, error_msg, None


def schedule_content_on_iot_devices(
    schedule_data: Dict[str, Any],
    playlists_table_name: str,
    contents_table_name: str,
    iot_api_url: str,
    default_s3_bucket: str
) -> Tuple[bool, List[str], List[Dict[str, Any]]]:
    """
    Schedule content on IoT devices after successful schedule creation.
    
    Args:
        schedule_data: Complete schedule data from database
        playlists_table_name: DynamoDB table name for playlists
        contents_table_name: DynamoDB table name for contents
        iot_api_url: IoT API endpoint URL
        default_s3_bucket: Default S3 bucket name
        
    Returns:
        Tuple of (overall_success, error_messages, iot_responses)
    """
    
    assigned_devices = schedule_data.get("assigned_to", [])
    playlists = schedule_data.get("playlists", [])
    contents = schedule_data.get("contents", [])
    start_at = schedule_data.get("start_at", "")
    end_at = schedule_data.get("end_at", "")
    schedule_id = schedule_data.get("id", "")
    
    print(f"Starting IoT scheduling for schedule {schedule_id}")
    print(f"Assigned devices: {assigned_devices}")
    print(f"Playlists: {playlists}")
    print(f"Contents: {contents}")
    
    # Collect all content information
    content_list, content_errors = collect_contents_from_playlists_and_contents(
        playlists, contents, playlists_table_name, contents_table_name, default_s3_bucket
    )
    
    if not content_list:
        error_msg = "No valid contents found for scheduling"
        if content_errors:
            error_msg += f". Errors: {'; '.join(content_errors)}"
        return False, [error_msg], []
    
    print(f"Collected {len(content_list)} contents for scheduling")
    
    error_messages = content_errors.copy()  # Start with content collection errors
    iot_responses = []
    successful_devices = 0
    
    # Schedule content on each assigned device
    for device_id in assigned_devices:
        # Generate unique playback ID for this device
        playback_id = int(time.time() * 1000);
        
        success, error, response_data = call_iot_schedule_api(
            device_id=device_id,
            schedule_time=start_at,
            schedule_time_end=end_at,
            playback_id=playback_id,
            contents=content_list,
            iot_api_url=iot_api_url
        )
        
        if success:
            successful_devices += 1
            iot_responses.append({
                "device_id": device_id,
                "playback_id": playback_id,
                "status": "success",
                "response": response_data
            })
        else:
            error_messages.append(f"Device {device_id}: {error}")
            iot_responses.append({
                "device_id": device_id,
                "playback_id": playback_id,
                "status": "failed",
                "error": error
            })
    
    overall_success = successful_devices > 0  # Success if at least one device was scheduled
    
    print(f"IoT scheduling completed. Success: {overall_success}")
    print(f"Successful devices: {successful_devices}/{len(assigned_devices)}")
    
    return overall_success, error_messages, iot_responses
