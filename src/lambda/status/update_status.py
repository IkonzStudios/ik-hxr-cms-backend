import json
import os
from typing import Dict, Any, Optional
from datetime import datetime

from utils.helpers import (
    parse_request_body,
    create_error_response,
    get_cors_headers,
)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to handle IoT device status updates.
    
    Expected event structure:
    {
        "body": {
            "timestamp": "2025-09-05T09:52:32.050217+00:00",
            "thingName": "fedora-device-b2c92d792f1c4971bc6ff42c9776b58b",
            "jobId": "delete-test_cl-5-31032d55-ece2-4edb-8f3b-a01a5cd5327a",
            "step": "DELETE_1_SUCCESS",
            "message": "Successfully deleted 'hxr/vid3_new.mp4'."
        }
    }
    """

    try:
        # Debug: Print the event structure
        print(f"Event: {json.dumps(event)}")
        print(f"Event keys: {list(event.keys())}")
        print(f"Body key exists: {'body' in event}")
        print(f"Body value: {event.get('body')}")
        print(f"Body type: {type(event.get('body'))}")

        # Parse request body
        body, parse_error = parse_request_body(event)
        if parse_error:
            return parse_error

        # Validate required fields
        required_fields = ["timestamp", "thingName", "jobId", "step", "message"]
        for field in required_fields:
            if field not in body:
                return create_error_response(400, f"Missing required field: {field}")

        # Extract data
        timestamp = body["timestamp"]
        device_id = body["thingName"]  # thingName is the device_id
        content_id = body["contentId"] | 'None'
        job_id = body["jobId"]
        step = body["step"]
        message = body["message"]

        print(f"Processing status update:")
        print(f"  Device ID: {device_id}")
        print(f"  Content ID: {content_id}")
        print(f"  Job ID: {job_id}")
        print(f"  Step: {step}")
        print(f"  Message: {message}")
        print(f"  Timestamp: {timestamp}")

        # Route to appropriate handler based on step type
        result = route_status_update(device_id, content_id, job_id, step, message, timestamp, body)

        return {
            "statusCode": 200,
            "headers": get_cors_headers(),
            "body": json.dumps({
                "message": "Status update processed successfully",
                "device_id": device_id,
                "content_id": content_id,
                "job_id": job_id,
                "step": step,
                "result": result
            }),
        }

    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        print(f"Error processing status update: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, "Internal server error")


def route_status_update(device_id: str, content_id: str, job_id: str, step: str, message: str, timestamp: str, full_body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Route the status update to the appropriate handler based on step type.
    """
    
    # Define step categories
    loop_update_steps = ["LOOP_UPDATE_FAILED", "LOOP_REPLACE_SUCCESS", "LOOP_REPLACE_FAILED"]
    schedule_steps = ["VERIFY_CONTENT_STARTED", "VERIFY_CONTENT_SUCCESS", "CREATE_PLAYLIST_STARTED", "CREATE_PLAYLIST_SUCCESS"]
    delete_steps = ["DELETE_1_SUCCESS", "DELETE_1_SKIPPED", "DELETE_1_FAILED", "DELETE_2_SUCCESS", "DELETE_2_SKIPPED", "DELETE_2_FAILED", "DELETE_3_SUCCESS", "DELETE_3_SKIPPED", "DELETE_3_FAILED"]
    assign_steps = ["DOWNLOAD_1_SKIPPED", "DOWNLOAD_1_STARTED", "DOWNLOAD_1_SUCCESS", "DOWNLOAD_1_FAILED", "DOWNLOAD_2_SKIPPED", "DOWNLOAD_2_STARTED", "DOWNLOAD_2_SUCCESS", "DOWNLOAD_2_FAILED", "DOWNLOAD_3_SKIPPED", "DOWNLOAD_3_STARTED", "DOWNLOAD_3_SUCCESS", "DOWNLOAD_3_FAILED"]
    
    # Check if step matches any known patterns
    if step in loop_update_steps:
        # TODO:
        return handle_loop_update(device_id, job_id, step, message, timestamp, full_body)
    elif step in schedule_steps:
        # TODO:
        return handle_schedule_content(device_id, job_id, step, message, timestamp, full_body)
    elif step in delete_steps:
        # TODO:
        return handle_delete_content(device_id, job_id, step, message, timestamp, full_body)
    elif step in assign_steps:
        return handle_assign_content(device_id, content_id, job_id, step, message, timestamp, full_body)
    else:
        return {
            "status": "unknown_step",
            "message": f"Unknown step type: {step}",
            "action": "logged_only"
        }


def handle_loop_update(device_id: str, job_id: str, step: str, message: str, timestamp: str, full_body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle Loop Video Update steps:
    - LOOP_UPDATE_FAILED
    - LOOP_REPLACE_SUCCESS  
    - LOOP_REPLACE_FAILED
    """
    print(f"Handling Loop Update: {step}")
    
    # TODO: Implement loop update logic
    # 1. Validate device exists
    # 2. Update device status in database
    # 3. Log the update
    # 4. Handle success/failure notifications
    
    return {
        "handler": "loop_update",
        "step": step,
        "status": "processed",
        "todo": "Implement device validation and database updates"
    }


def handle_schedule_content(device_id: str, job_id: str, step: str, message: str, timestamp: str, full_body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle Schedule Content / Create Playlist steps:
    - VERIFY_CONTENT_STARTED
    - VERIFY_CONTENT_SUCCESS
    - CREATE_PLAYLIST_STARTED
    - CREATE_PLAYLIST_SUCCESS
    """
    print(f"Handling Schedule Content: {step}")
    
    # TODO: Implement schedule content logic
    # 1. Validate device exists
    # 2. Update device content verification status
    # 3. Update playlist creation status
    # 4. Log the update
    
    return {
        "handler": "schedule_content",
        "step": step,
        "status": "processed",
        "todo": "Implement content verification and playlist status updates"
    }


def handle_delete_content(device_id: str, job_id: str, step: str, message: str, timestamp: str, full_body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle Delete Content steps:
    - DELETE_n_SUCCESS
    - DELETE_n_SKIPPED
    - DELETE_n_FAILED
    """
    print(f"Handling Delete Content: {step}")
    
    # Extract content index from step (e.g., "DELETE_1_SUCCESS" -> "1")
    try:
        content_index = step.split("_")[1]
    except IndexError:
        content_index = "unknown"
    
    # TODO: Implement delete content logic
    # 1. Validate device exists
    # 2. Update device content status
    # 3. Remove content from device content arrays
    # 4. Log the deletion result
    
    return {
        "handler": "delete_content",
        "step": step,
        "content_index": content_index,
        "status": "processed",
        "todo": "Implement content removal from device arrays"
    }


def handle_assign_content(device_id: str, content_id: str, job_id: str, step: str, message: str, timestamp: str, full_body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle Assign Content steps:
    - DOWNLOAD_n_SKIPPED
    - DOWNLOAD_n_STARTED
    - DOWNLOAD_n_SUCCESS
    - DOWNLOAD_n_FAILED
    """
    print(f"Handling Assign Content: {step}")
    
    # Extract content index from step (e.g., "DOWNLOAD_1_SUCCESS" -> "1")
    try:
        content_index = step.split("_")[1]
    except IndexError:
        content_index = "unknown"
    
    # TODO: Implement assign content logic
    # 1. Validate device exists
    # 2. Update device content download status
    # 3. Move content between status arrays (initiated -> downloading -> downloaded)
    # 4. Log the download result
    
    return {
        "handler": "assign_content",
        "step": step,
        "content_index": content_index,
        "status": "processed",
        "todo": "Implement content status array updates"
    }
