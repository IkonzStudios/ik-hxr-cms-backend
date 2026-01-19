"""
IoT application scheduling utilities for schedule management.
"""

import json
import os
import requests
import time
from typing import Dict, Any, List, Tuple, Optional
import boto3
from utils.helpers import get_application_by_id


def call_iot_application_schedule_api(
    device_id: str, 
    schedule_time: str, 
    schedule_time_end: str, 
    playback_id: str, 
    applications: List[Dict[str, str]],
    iot_api_url: str
) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Call the external IoT scheduling API for a single device with applications.
    
    Args:
        device_id: Device ID to schedule applications for
        schedule_time: Start time in ISO format
        schedule_time_end: End time in ISO format
        playback_id: Unique schedule ID (used as scheduleId)
        applications: List of application dicts with flatpakAppId and type
        iot_api_url: IoT API endpoint URL
        
    Returns:
        Tuple of (success, error_message, response_data)
    """
    # Transform applications to match the required payload structure
    content_payload = {
        "url": applications[0]["url"]
    }

    schedule_type = "url_" + applications[0]["type"].lower();

    payload = {
        "action": "schedule_content",
        "thingName": device_id,
        "payload": {
            "scheduleId": str(playback_id),  # Use playback_id as scheduleId
            "scheduleType": schedule_type,
            "scheduleStartTime": schedule_time,
            "scheduleEndTime": schedule_time_end,
            "contentPayload": content_payload
        }
    }
    
    try:
        print(f"Calling IoT API for device {device_id} with applications")
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


def schedule_applications_on_iot_devices(
    schedule_data: Dict[str, Any],
    applications_table_name: str,
    iot_api_url: str
) -> Tuple[bool, List[str], List[Dict[str, Any]]]:
    """
    Schedule applications on IoT devices after successful schedule creation.
    
    Args:
        schedule_data: Complete schedule data from database
        applications_table_name: DynamoDB table name for applications
        iot_api_url: IoT API endpoint URL
        
    Returns:
        Tuple of (overall_success, error_messages, iot_responses)
    """
    
    assigned_devices = schedule_data.get("assigned_to", [])
    applications = schedule_data.get("applications", [])
    start_at = schedule_data.get("start_at", "")
    end_at = schedule_data.get("end_at", "")
    schedule_id = schedule_data.get("id", "")
    playback_id = schedule_data.get("playback_id", "")
    
    print(f"Starting IoT application scheduling for schedule {schedule_id}")
    print(f"Assigned devices: {assigned_devices}")
    print(f"Applications: {applications}")
    
    # Collect all application information
    application_list, application_errors = collect_applications_from_ids(
        applications, applications_table_name
    )
    
    if not application_list:
        error_msg = "No valid applications found for scheduling"
        if application_errors:
            error_msg += f". Errors: {'; '.join(application_errors)}"
        return False, [error_msg], []
    
    print(f"Collected {len(application_list)} applications for scheduling")
    
    error_messages = application_errors.copy()  # Start with application collection errors
    iot_responses = []
    successful_devices = 0
    
    # Schedule applications on each assigned device
    for device_id in assigned_devices:
        success, error, response_data = call_iot_application_schedule_api(
            device_id=device_id,
            schedule_time=start_at,
            schedule_time_end=end_at,
            playback_id=playback_id,
            applications=application_list,
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
    
    print(f"IoT application scheduling completed. Success: {overall_success}")
    print(f"Successful devices: {successful_devices}/{len(assigned_devices)}")
    
    return overall_success, error_messages, iot_responses


def collect_applications_from_ids(
    application_ids: List[str], 
    applications_table_name: str
) -> Tuple[List[Dict[str, str]], List[str]]:
    """
    Collect all application information from application IDs.
    
    Args:
        application_ids: List of application IDs
        applications_table_name: DynamoDB table name for applications
        
    Returns:
        Tuple of (application_list, error_messages)
        application_list: List of dicts with flatpakAppId and type
        error_messages: List of error messages encountered
    """
    application_list = []
    error_messages = []
    
    # Process each application
    for application_id in application_ids:
        application_data, error = get_application_by_id(application_id, applications_table_name)
        if error:
            error_messages.append(f"Application error: {error}")
            continue
            
        # Extract application information for IoT scheduling
        # For now, we'll use the application name as flatpakAppId and set type to "PWA"
        # This can be enhanced based on actual application data structure
        # flatpak_app_id = f"/opt/{application_data.get('name', 'unknown')}/{application_data.get('name', 'unknown').lower().replace(' ', '-')}"
        
        application_list.append({
            "type": application_data.get("type", "PWA"),
            "url": application_data.get("url", "")
        })
    
    return application_list, error_messages
