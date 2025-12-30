import json
import os
import requests
from typing import Dict, Any, Optional
from utils.helpers import (
    get_schedule_by_id_from_db,
    delete_schedule_from_db,
    create_error_response,
    get_cors_headers,
)
from utils.rbac import check_delete_permission_with_org


def call_iot_delete_schedule_api(
    device_id: str,
    job_id: str,
    iot_delete_api_url: str
) -> tuple[bool, Optional[str]]:
    """
    Call the external IoT delete schedule API.
    
    Args:
        device_id: Device ID (thingName)
        job_id: Job ID to use as scheduleId
        iot_delete_api_url: IoT delete API endpoint URL
        
    Returns:
        Tuple of (success, error_message)
    """
    payload = {
        "action": "delete_schedule",
        "thingName": device_id,
        "payload": {
            "scheduleId": job_id
        }
    }
    
    try:
        print(f"Calling IoT delete API for device {device_id} with job_id {job_id}")
        print(f"Payload: {json.dumps(payload, indent=2)}")
        
        response = requests.post(
            iot_delete_api_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        print(f"IoT Delete API Response Status: {response.status_code}")
        print(f"IoT Delete API Response: {response.text}")
        
        if response.status_code == 200:
            return True, None
        else:
            return False, f"IoT API returned status {response.status_code}: {response.text}"
            
    except requests.exceptions.RequestException as e:
        error_msg = f"Failed to call IoT delete API for device {device_id}: {str(e)}"
        print(error_msg)
        return False, error_msg


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to delete a schedule by ID from DynamoDB.
    
    First calls the IoT delete API, then deletes from DynamoDB on success.

    Expected event structure:
    {
        "pathParameters": {
            "id": "schedule-uuid"
        }
    }
    """

    try:
        # Get environment variables
        schedules_table_name = os.environ.get("SCHEDULES_TABLE_NAME")
        device_table_name = os.environ.get("DEVICES_TABLE_NAME")
        iot_delete_api_url = os.environ.get("IOT_DELETE_API_URL")
        
        if not schedules_table_name:
            raise ValueError("SCHEDULES_TABLE_NAME environment variable not set")
        if not device_table_name:
            raise ValueError("DEVICES_TABLE_NAME environment variable not set")
        if not iot_delete_api_url:
            raise ValueError("IOT_DELETE_API_URL environment variable not set")

        # Debug: Print the event structure
        print(f"Event: {json.dumps(event)}")

        # Extract schedule ID from path parameters
        path_parameters = event.get("pathParameters", {})
        schedule_id = path_parameters.get("id") if path_parameters else None

        if not schedule_id:
            return create_error_response(400, "Schedule ID is required")

        # Get schedule from database to check organization and get job_id
        schedule, get_error = get_schedule_by_id_from_db(schedule_id, schedules_table_name)
        if get_error:
            return get_error

        # RBAC: Check if user has permission to delete schedules in this organization
        rbac_error, user_info = check_delete_permission_with_org(
            event, "schedule", schedule["organization_id"]
        )
        if rbac_error:
            return rbac_error

        # Log user action for audit
        print(f"User {user_info['user_id']} ({user_info['role']}) deleting schedule {schedule_id}")

        # Get job_id and assigned devices from schedule
        job_id = schedule.get("job_id", "")
        assigned_devices = schedule.get("assigned_to", [])

        # If no devices assigned, just delete from DB
        if not assigned_devices:
            delete_error = delete_schedule_from_db(
                schedule_id, schedules_table_name, device_table_name
            )
            if delete_error:
                return delete_error

            return {
                "statusCode": 200,
                "headers": get_cors_headers(),
                "body": json.dumps({
                    "message": "Schedule deleted successfully",
                    "data": {"id": schedule_id}
                }),
            }

        # If no job_id but devices are assigned, we can't delete from IoT devices
        # but we should still allow deletion from DB (schedule may have failed to schedule)
        if not job_id:
            print(f"Warning: Schedule {schedule_id} has assigned devices but no job_id. Deleting from DB only.")
            delete_error = delete_schedule_from_db(
                schedule_id, schedules_table_name, device_table_name
            )
            if delete_error:
                return delete_error

            return {
                "statusCode": 200,
                "headers": get_cors_headers(),
                "body": json.dumps({
                    "message": "Schedule deleted from database (no job_id found, could not delete from IoT devices)",
                    "data": {"id": schedule_id},
                    "warning": "Schedule was not deleted from IoT devices due to missing job_id"
                }),
            }

        # Call IoT delete API for each assigned device
        iot_success = False
        iot_errors = []
        
        for device_id in assigned_devices:
            success, error = call_iot_delete_schedule_api(
                device_id=device_id,
                job_id=job_id,
                iot_delete_api_url=iot_delete_api_url
            )
            
            if success:
                iot_success = True
            else:
                iot_errors.append(f"Device {device_id}: {error}")

        # Only delete from DynamoDB if at least one IoT delete was successful
        if iot_success:
            delete_error = delete_schedule_from_db(
                schedule_id, schedules_table_name, device_table_name
            )
            if delete_error:
                return delete_error

            response_message = "Schedule deleted successfully"
            if iot_errors:
                response_message += f" with some IoT errors: {'; '.join(iot_errors)}"

            return {
                "statusCode": 200,
                "headers": get_cors_headers(),
                "body": json.dumps({
                    "message": response_message,
                    "data": {"id": schedule_id},
                    "iot_errors": iot_errors if iot_errors else None
                }),
            }
        else:
            # All IoT deletions failed
            return {
                "statusCode": 500,
                "headers": get_cors_headers(),
                "body": json.dumps({
                    "error": "Failed to delete schedule from IoT devices",
                    "iot_errors": iot_errors
                }),
            }

    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        print(f"Error deleting schedule: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback

        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, "Internal server error")

