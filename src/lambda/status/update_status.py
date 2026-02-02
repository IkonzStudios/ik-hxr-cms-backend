import json
import os
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

import boto3

from utils.helpers import (
    parse_request_body,
    create_error_response,
    get_cors_headers,
)

def get_device_environment(device_id: str) -> str:
    """
    Determine which environment a device belongs to.
    
    Args:
        device_id: The device ID to check
        
    Returns:
        Environment name: 'prod', 'stage', or 'dev'
    """
    # Get device-environment mapping from table
    try:
        table_name = os.environ.get("DEVICES_TABLE_NAME_FOR_STAGE_AND_DEV")
        if not table_name:
            raise ValueError("DEVICES_TABLE_NAME_FOR_STAGE_AND_DEV environment variable not set")
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)

        response = table.scan()
        devices = response["Items"];
        print(f"Devices: {devices}")
        for device in devices:
            if device["id"] == device_id:
                return device["environment"]
        return "prod"  # Default to prod if not found
    except Exception as e:
        print(f"Error getting device environment: {str(e)}")
        return "prod"

def forward_to_environment_api(event: Dict[str, Any], target_env: str) -> Dict[str, Any]:
    """
    Forward the request to another environment's API.
    
    Args:
        event: The original Lambda event
        target_env: Target environment ('stage' or 'dev')
        
    Returns:
        API Gateway response dict
    """
    try:
        import requests
    except ImportError:
        return create_error_response(500, "requests library not available for API forwarding")
    
    # Get target environment API URL
    env_urls = {
        "stage": os.environ.get("STAGE_API_URL"),
        "dev": os.environ.get("DEV_API_URL")
    }
    
    target_url = env_urls.get(target_env)
    if not target_url:
        return create_error_response(500, f"No API URL configured for environment: {target_env}")
    
    # Extract body from event
    if isinstance(event.get("body"), str):
        body_data = json.loads(event.get("body", "{}"))
    else:
        body_data = event.get("body", {})
    
    print(f"Forwarding request to {target_env} environment: {target_url}")
    
    try:
        # Forward the request to the target environment
        response = requests.post(
            target_url + '/status',
            json=body_data,
            headers={"Content-Type": "application/json"},
            timeout=30  # 30 second timeout
        )
        
        # Return the response from the target environment
        return {
            "statusCode": response.status_code,
            "headers": get_cors_headers(),
            "body": response.text
        }
    except requests.exceptions.RequestException as e:
        print(f"Error forwarding request to {target_env}: {str(e)}")
        return create_error_response(502, f"Failed to forward request to {target_env} environment")


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to queue IoT device status updates for sequential processing.
    
    This function receives status updates from IoT Core and queues them in SQS
    to ensure they are processed sequentially, avoiding race conditions.
    
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
        content_key = body.get("key", "None")
        job_id = body["jobId"]
        step = body["step"]
        message = body["message"]

        print(f"Queuing status update:")
        print(f"  Device ID: {device_id}")
        print(f"  Content Key: {content_key}")
        print(f"  Job ID: {job_id}")
        print(f"  Step: {step}")
        print(f"  Message: {message}")
        print(f"  Timestamp: {timestamp}")

        # ============ ENVIRONMENT ROUTING LOGIC ============
        # Check which environment this device belongs to
        device_env = get_device_environment(device_id)
        current_env = os.environ.get("ENV", "prod")

        print(f"Device {device_id} belongs to environment: {device_env}")
        print(f"Current environment: {current_env}")

        # If device belongs to a different environment (stage or dev), forward the request
        if device_env != current_env and device_env in ["stage", "dev"]:
            print(f"Forwarding device {device_id} request from {current_env} to {device_env}")
            return forward_to_environment_api(event, device_env)
        
        # If device belongs to prod or current environment, continue with normal processing
        print(f"Processing device {device_id} locally in {current_env} environment")
        # ===================================================

        # Get SQS queue URL from environment
        queue_url = os.environ.get("STATUS_UPDATE_QUEUE_URL")
        if not queue_url:
            return create_error_response(500, "STATUS_UPDATE_QUEUE_URL environment variable not set")

        # Create SQS client
        sqs_client = boto3.client('sqs')

        # Send message to SQS queue
        try:
            response = sqs_client.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(body),
                MessageGroupId=device_id,  # Ensure per-device ordering in FIFO queue
                MessageAttributes={
                    'device_id': {
                        'StringValue': device_id,
                        'DataType': 'String'
                    },
                    'step': {
                        'StringValue': step,
                        'DataType': 'String'
                    },
                    'job_id': {
                        'StringValue': job_id,
                        'DataType': 'String'
                    },
                    'timestamp': {
                        'StringValue': timestamp,
                        'DataType': 'String'
                    }
                }
            )
            
            print(f"Message queued successfully: {response['MessageId']}")
            
            return {
                "statusCode": 200,
                "headers": get_cors_headers(),
                "body": json.dumps({
                    "message": "Status update queued successfully",
                    "device_id": device_id,
                    "content_key": content_key,
                    "job_id": job_id,
                    "step": step,
                    "message_id": response['MessageId']
                }),
            }
            
        except Exception as sqs_error:
            print(f"Error sending message to SQS: {str(sqs_error)}")
            return create_error_response(500, f"Failed to queue status update: {str(sqs_error)}")

    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        print(f"Error processing status update: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, "Internal server error")

