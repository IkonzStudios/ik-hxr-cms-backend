import json
import os
import traceback
import uuid
import boto3
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, Any, Tuple, Optional

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
        contents_table_name = os.environ.get("CONTENTS_TABLE_NAME")
        playbacks_table_name = os.environ.get("PLAYBACKS_TABLE_NAME")
        schedules_table_name = os.environ.get("SCHEDULES_TABLE_NAME")

        if not table_name:
            raise ValueError("DEVICES_TABLE_NAME environment variable not set")
        if not playbacks_table_name:
            raise ValueError("PLAYBACKS_TABLE_NAME environment variable not set")
        if not contents_table_name:
            raise ValueError("CONTENTS_TABLE_NAME environment variable not set")
        if not schedules_table_name:
            raise ValueError("SCHEDULES_TABLE_NAME environment variable not set")

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
        # unexpected_fields = body_fields - expected_fields
        # if unexpected_fields:
        #     return create_error_response(400, f"Unexpected fields in request body: {', '.join(unexpected_fields)}")

        device_id = body["device_id"]
        cpu_usage = body["cpu_usage"]
        memory_usage = body["memory_usage"]

        # Validate cpu_usage and memory_usage
        try:
            # Handle empty strings by converting to 0.0
            if cpu_usage == "" or cpu_usage is None:
                cpu_usage = 0.0
            else:
                cpu_usage = float(cpu_usage)
            
            if memory_usage == "" or memory_usage is None:
                memory_usage = 0.0
            else:
                memory_usage = float(memory_usage)
        except (ValueError, TypeError):
            return create_error_response(400, "cpu_usage and memory_usage must be valid numbers")

        # First get the existing device to verify it exists
        existing_device, get_error = get_device_by_id_from_db(device_id, table_name)
        if get_error:
            return get_error
        
        base_content_id = existing_device.get("base_content_id", "")

        # Update the last_seen timestamp
        ist_timezone = timezone(timedelta(hours=5, minutes=30))
        current_time = datetime.now(ist_timezone).isoformat()
        current_date = datetime.now(ist_timezone).date()

        start_at = existing_device.get("start_at", current_time)
        last_seen = existing_device.get("last_seen", current_time)
        last_seen_date = datetime.fromisoformat(last_seen.replace('Z', '+00:00')).astimezone(ist_timezone).date()


        # If last_seen date is before today
        if last_seen_date < current_date:
            # Convert ISO strings to datetime objects for subtraction
            last_seen_dt = datetime.fromisoformat(last_seen.replace('Z', '+00:00')).astimezone(ist_timezone)
            start_at_dt = datetime.fromisoformat(start_at.replace('Z', '+00:00')).astimezone(ist_timezone)
            print(f"Device Id: {device_id}")
            # start_at - last_seen --> total machine seconds running
            total_machine_seconds_running = (last_seen_dt - start_at_dt).total_seconds()
            print(f"Total machine seconds running: {total_machine_seconds_running}")

            schedule_ids = existing_device.get("schedules", [])
            if isinstance(schedule_ids, str):
                schedule_ids = json.loads(schedule_ids)

            print(f"Schedule ids: {schedule_ids}")
            # total schedule seconds
            total_schedule_seconds, schedule_error = get_all_last_seen_date_schedules_duration_from_db(schedule_ids, schedules_table_name, last_seen_date);
            if schedule_error:
                return schedule_error
            print(f"Total schedule seconds: {total_schedule_seconds}")

            # total machine seconds running - total schedule seconds = base content running
            base_content_running = total_machine_seconds_running - total_schedule_seconds
            print(f"Base content running: {base_content_running}")

            dynamodb = boto3.resource("dynamodb")
            content_table = dynamodb.Table(contents_table_name)
            playback_table = dynamodb.Table(playbacks_table_name)

            print(f"Base content id: {base_content_id}")
            if base_content_id:
                content_data = content_table.get_item(Key={"id": base_content_id})
                print(f"Content data: {content_data}")
                content = content_data.get("Item")
                print(f"Content: {content}")
                # Parse duration safely as float; content duration may be a decimal string like '28.76'
                duration_value = 1.0
                if content and content.get("duration"):
                    try:
                        duration_value = float(content.get("duration", 1))
                    except (ValueError, TypeError):
                        print(f"Invalid duration for content {base_content_id}: {content.get('duration')}. Defaulting to 1s.")
                # Avoid zero/negative values
                duration_value = max(duration_value, 1e-6)
                base_content_seconds = max(float(base_content_running), 0.0)
                print(f"Duration (s): {duration_value}")
                times_played = int(base_content_seconds / duration_value)
                print(f"Times played: {times_played}")
                playback_table.put_item(
                    Item={
                        "id": str(uuid.uuid4()),
                        "content_id": base_content_id,
                        "created_at": current_time,
                        "device_id": device_id,
                        "duration": str(duration_value),
                        "end_at": last_seen,
                        "job_id": "",
                        "organization_id": existing_device.get("organization_id", ""),
                        "schedule_id": "",
                        "start_at": start_at,
                        "status": "ended",
                        "times_played": times_played,
                        "updated_at": current_time,
                    }
                )

            start_at = current_time
        else:
            print("Last seen date is today...")
            print(f"current_time: {current_time}")


        update_error = update_device_last_seen_in_db(device_id, start_at, current_time, cpu_usage, memory_usage, table_name)
        if update_error:
            return update_error

        # Return success response
        return {
            "statusCode": 200,
            "headers": get_cors_headers(),
            "body": json.dumps({
                "message": "Device last_seen timestamp updated successfully",
                "device_id": device_id,
                "last_seen": current_time,
                "cpu_usage": cpu_usage,
                "memory_usage": memory_usage
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
    device_id: str, start_at: str, last_seen: str, cpu_usage: float, memory_usage: float, table_name: str
) -> None:
    """
    Update a device's last_seen timestamp in DynamoDB.

    Args:
        device_id: The device ID to update
        start_at: The new start_at timestamp (ISO format)
        last_seen: The new last_seen timestamp (ISO format)
        cpu_usage: The new cpu_usage value
        memory_usage: The new memory_usage value
        table_name: The DynamoDB table name

    Returns:
        None if successful, raises exception if failed
    """
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)

        table.update_item(
            Key={"id": device_id},
            UpdateExpression="SET #start_at = :start_at, #last_seen = :last_seen, #cpu_usage = :cpu_usage, #memory_usage = :memory_usage",
            ExpressionAttributeNames={
                "#start_at": "start_at",
                "#last_seen": "last_seen",
                "#cpu_usage": "cpu_usage",
                "#memory_usage": "memory_usage"
            },
            ExpressionAttributeValues={
                ":start_at": start_at,
                ":last_seen": last_seen,
                ":cpu_usage": Decimal(str(cpu_usage)),
                ":memory_usage": Decimal(str(memory_usage))
            },
            ConditionExpression="attribute_exists(id)",
        )

    except Exception as e:
        print(f"Error updating device last_seen in database: {str(e)}")
        if "ConditionalCheckFailedException" in str(e):
            raise ValueError("Device not found")
        raise e


def get_all_last_seen_date_schedules_duration_from_db(schedule_ids: list, schedules_table_name: str, last_seen_date) -> Tuple[float, Optional[Dict[str, Any]]]:
    """
    Get all schedules duration for the last_seen_date from DynamoDB.
    """
    try:
        if not schedule_ids:
            return 0, None
            
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(schedules_table_name)
        
        # Get IST timezone
        ist_timezone = timezone(timedelta(hours=5, minutes=30))
        
        # Calculate last_seen_date's start and end times
        last_seen_start = datetime.combine(last_seen_date, datetime.min.time()).replace(tzinfo=ist_timezone)
        last_seen_end = datetime.combine(last_seen_date, datetime.max.time()).replace(tzinfo=ist_timezone)
        
        # Build the IN clause dynamically for the filter expression
        # Create placeholders for each schedule ID
        id_placeholders = [f":id{i}" for i in range(len(schedule_ids))]
        in_clause = f"id IN ({', '.join(id_placeholders)})"
        
        # Create expression attribute values for the IN clause
        expression_attribute_values = {f":id{i}": schedule_id for i, schedule_id in enumerate(schedule_ids)}
        
        # Add the date range values
        expression_attribute_values[":last_seen_start"] = last_seen_start.isoformat()
        expression_attribute_values[":last_seen_end"] = last_seen_end.isoformat()
        
        # Build the complete filter expression
        filter_expression = f"{in_clause} AND start_at BETWEEN :last_seen_start AND :last_seen_end"
        
        response = table.scan(
            FilterExpression=filter_expression,
            ExpressionAttributeValues=expression_attribute_values
        )
        
        schedules = response["Items"]
        total_schedule_seconds = sum([(datetime.fromisoformat(schedule["end_at"].replace('Z', '+00:00')).astimezone(ist_timezone) - datetime.fromisoformat(schedule["start_at"].replace('Z', '+00:00')).astimezone(ist_timezone)).total_seconds() for schedule in schedules])
        return total_schedule_seconds, None
    except Exception as e:
        print(f"Error getting all last_seen_date schedules duration from database: {str(e)}")
        return 0, {"statusCode": 500, "body": json.dumps({"error": "Internal server error"})}
