import json
import os
import traceback
import boto3
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

from utils.helpers import (
    parse_request_body,
    get_device_by_id_from_db,
    create_error_response,
    get_cors_headers,
)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to update a device's last_seen timestamp in DynamoDB.

    Expected event structure:
    {
        "body": {
            "device_id": "fedora-device-b2c92d792f1c4971bc6ff42c9776b58b",
            "ip_address": "10.171.21.243",
            "cpu_usage": 39.8,
            "memory_usage": 52.5
        }
    }
    """

    try:
        # Get table name from environment variable
        table_name = os.environ.get("DEVICES_TABLE_NAME")
        if not table_name:
            raise ValueError("DEVICES_TABLE_NAME environment variable not set")

        # Debug: Print the event structure
        print(f"Event: {json.dumps(event)}")

        # Parse request body
        body, parse_error = parse_request_body(event)
        if parse_error:
            return parse_error

        # Check if body has device_id
        if not body or not body.get("device_id"):
            return create_error_response(400, "device_id is required in request body")

        # Validate expected structure - only allow device_id, ip_address, cpu_usage, memory_usage
        expected_fields = {"device_id", "ip_address", "cpu_usage", "memory_usage"}
        body_fields = set(body.keys())
        
        # Check for unexpected fields
        unexpected_fields = body_fields - expected_fields
        if unexpected_fields:
            return create_error_response(400, f"Unexpected fields in request body: {', '.join(unexpected_fields)}")

        device_id = body["device_id"]

        # First get the existing device to verify it exists
        existing_device, get_error = get_device_by_id_from_db(device_id, table_name)
        if get_error:
            return get_error

        # Update the last_seen timestamp
        ist_timezone = timezone(timedelta(hours=5, minutes=30))
        current_time = datetime.now(ist_timezone).isoformat()
        update_error = update_device_last_seen_in_db(device_id, current_time, table_name)
        if update_error:
            return update_error

        # Return success response
        return {
            "statusCode": 200,
            "headers": get_cors_headers(),
            "body": json.dumps({
                "message": "Device last_seen timestamp updated successfully",
                "device_id": device_id,
                "last_seen": current_time
            }),
        }

    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        print(f"Error updating device last_seen: {str(e)}")
        print(f"Error type: {type(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, "Internal server error")


def update_device_last_seen_in_db(
    device_id: str, last_seen: str, table_name: str
) -> None:
    """
    Update a device's last_seen timestamp in DynamoDB.

    Args:
        device_id: The device ID to update
        last_seen: The new last_seen timestamp (ISO format)
        table_name: The DynamoDB table name

    Returns:
        None if successful, raises exception if failed
    """
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)

        table.update_item(
            Key={"id": device_id},
            UpdateExpression="SET #last_seen = :last_seen",
            ExpressionAttributeNames={
                "#last_seen": "last_seen"
            },
            ExpressionAttributeValues={
                ":last_seen": last_seen
            },
            ConditionExpression="attribute_exists(id)",
        )

    except Exception as e:
        print(f"Error updating device last_seen in database: {str(e)}")
        if "ConditionalCheckFailedException" in str(e):
            raise ValueError("Device not found")
        raise e
