import json
import os
from typing import Dict, Any
from utils.helpers import (
    parse_request_body,
    get_device_by_id_from_db,
    prepare_update_data,
    update_device_in_db,
    create_device_response,
    create_error_response
)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to update a device by ID in DynamoDB.
    
    Expected event structure:
    {
        "pathParameters": {
            "id": "device-uuid"
        },
        "body": {
            "name": "Updated Device Name",
            "description": "Updated Description",
            "model": "Updated Model",
            "version": "2.0.0",
            "ip_address": "192.168.1.101",
            "playlists": "[\"updated_playlist1\"]",
            "applications": "[\"updated_app1\"]",
            "contents": "[\"updated_content1\"]",
            "status": "inactive",
            "storage_left": 80.0,
            "storage_consumed": 70.0
        }
    }
    """
    
    try:
        # Get table name from environment variable
        table_name = os.environ.get('DEVICES_TABLE_NAME')
        if not table_name:
            raise ValueError("DEVICES_TABLE_NAME environment variable not set")
        
        # Debug: Print the event structure
        print(f"Event: {json.dumps(event)}")
        
        # Extract device ID from path parameters
        path_parameters = event.get('pathParameters', {})
        device_id = path_parameters.get('id') if path_parameters else None
        
        if not device_id:
            return create_error_response(400, 'Device ID is required')
        
        # Parse request body
        body, parse_error = parse_request_body(event)
        if parse_error:
            return parse_error
        
        # Check if body has any updateable fields
        if not body:
            return create_error_response(400, 'Request body cannot be empty')
        
        # Prepare update data
        update_data = prepare_update_data(body)
        
        if not update_data:
            return create_error_response(400, 'No valid fields to update')
        
        # Update device in database
        update_error = update_device_in_db(device_id, update_data, table_name)
        if update_error:
            return update_error
        
        # Get updated device to return in response
        updated_device, get_error = get_device_by_id_from_db(device_id, table_name)
        if get_error:
            return get_error
        
        # Return success response
        return create_device_response(updated_device)
        
    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        print(f"Error updating device: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, 'Internal server error')
