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

