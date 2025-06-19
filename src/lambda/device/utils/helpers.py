import json
import boto3
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Tuple, Optional
from .constants import REQUIRED_DEVICE_FIELDS


def parse_request_body(event: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Parse the request body from the event.
    
    Returns:
        Tuple of (parsed_body, error_response)
        If successful: (body_dict, None)
        If error: (None, error_response_dict)
    """
    body = None
    
    if 'body' in event:
        if isinstance(event['body'], str):
            try:
                body = json.loads(event['body'])
            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e}")
                return None, {
                    'statusCode': 400,
                    'body': json.dumps({
                        'error': 'Invalid JSON in request body'
                    })
                }
        elif isinstance(event['body'], dict):
            body = event['body']
        else:
            print(f"Unexpected body type: {type(event['body'])}")
            return None, {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Invalid request body format'
                })
            }
    
    # Ensure body is a dictionary
    if not isinstance(body, dict):
        print(f"Body is not a dictionary: {type(body)}")
        return None, {
            'statusCode': 400,
            'body': json.dumps({
                'error': 'Request body must be a JSON object'
            })
        }
    
    return body, None


def validate_required_fields(body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Validate that all required fields are present in the request body.
    
    Returns:
        None if validation passes, error response dict if validation fails
    """
    for field in REQUIRED_DEVICE_FIELDS:
        if not body.get(field['column_name']):
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': f'{field["name"]} is required'
                })
            }
    return None


def parse_array_fields(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse stringified array fields (playlists, applications, contents) from the body.
    
    Returns:
        Dictionary with parsed array values
    """
    result = {}
    
    for field_name in ['playlists', 'applications', 'contents']:
        field_value = body.get(field_name)
        if isinstance(field_value, str):
            try:
                result[field_name] = json.loads(field_value)
            except json.JSONDecodeError:
                result[field_name] = []
        elif field_value is None:
            result[field_name] = []
        else:
            result[field_name] = field_value
    
    return result


def convert_storage_values(body: Dict[str, Any]) -> Dict[str, Optional[Decimal]]:
    """
    Convert storage values to Decimal for DynamoDB compatibility.
    
    Returns:
        Dictionary with storage_left and storage_consumed as Decimal or None
    """
    result = {}
    
    storage_left = body.get('storage_left')
    if storage_left is not None:
        result['storage_left'] = Decimal(str(storage_left))
    else:
        result['storage_left'] = None
    
    storage_consumed = body.get('storage_consumed')
    if storage_consumed is not None:
        result['storage_consumed'] = Decimal(str(storage_consumed))
    else:
        result['storage_consumed'] = None
    
    return result


def create_device_data(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create the device data dictionary from the request body.
    
    Returns:
        Complete device data dictionary ready for DynamoDB
    """
    # Parse array fields
    arrays = parse_array_fields(body)
    
    # Convert storage values
    storage = convert_storage_values(body)
    
    # Generate device ID and timestamps
    device_id = str(uuid.uuid4())
    current_time = datetime.now().isoformat()
    
    # Create device data dictionary
    device_data = {
        "id": device_id,
        "name": body['name'],
        "organization_id": body['organization_id'],
        "description": body.get('description'),
        "model": body.get('model'),
        "version": body.get('version'),
        "ip_address": body.get('ip_address'),
        "playlists": arrays['playlists'],
        "applications": arrays['applications'],
        "contents": arrays['contents'],
        "status": body.get('status', 'active'),
        "last_seen": current_time,
        "last_updated": current_time,
        "storage_left": storage['storage_left'],
        "storage_consumed": storage['storage_consumed']
    }
    
    return device_data


def save_device_to_db(device_data: Dict[str, Any], table_name: str) -> Optional[Dict[str, Any]]:
    """
    Save device data to DynamoDB.
    
    Returns:
        None if successful, error response dict if failed
    """
    try:
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(table_name)
        
        table.put_item(
            Item=device_data,
            ConditionExpression='attribute_not_exists(id)'
        )
        return None
        
    except Exception as e:
        print(f"Error creating device: {str(e)}")
        print(f"Error type: {type(e)}")
        print(f"Error message: {str(e)}")
        return {
            'statusCode': 409,
            'body': json.dumps({
                'error': 'Device with this ID already exists'
            })
        }


def format_response_device(device_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format device data for JSON response by converting Decimal to float.
    
    Returns:
        Device data with Decimal values converted to float
    """
    response_device = device_data.copy()
    
    if response_device.get('storage_left') is not None:
        response_device['storage_left'] = float(response_device['storage_left'])
    if response_device.get('storage_consumed') is not None:
        response_device['storage_consumed'] = float(response_device['storage_consumed'])
    
    return response_device


def create_success_response(device_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a successful response for device creation.
    
    Returns:
        Success response dictionary
    """
    response_device = format_response_device(device_data)
    
    return {
        'statusCode': 201,
        'body': json.dumps({
            'message': 'Device created successfully',
            'device_id': device_data['id'],
            'device': response_device
        })
    }


def create_error_response(status_code: int, error_message: str) -> Dict[str, Any]:
    """
    Create an error response.
    
    Returns:
        Error response dictionary
    """
    return {
        'statusCode': status_code,
        'body': json.dumps({
            'error': error_message
        })
    }


def get_device_by_id_from_db(device_id: str, table_name: str) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Get a device by ID from DynamoDB.
    
    Returns:
        Tuple of (device_data, error_response)
        If successful: (device_dict, None)
        If error: (None, error_response_dict)
    """
    try:
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(table_name)
        
        response = table.get_item(Key={'id': device_id})
        
        if 'Item' not in response:
            return None, {
                'statusCode': 404,
                'body': json.dumps({
                    'error': 'Device not found'
                })
            }
        
        return response['Item'], None
        
    except Exception as e:
        print(f"Error getting device: {str(e)}")
        return None, {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Internal server error'
            })
        }


def get_devices_by_org_id_from_db(org_id: str, table_name: str) -> Tuple[Optional[list], Optional[Dict[str, Any]]]:
    """
    Get all devices by organization ID from DynamoDB.
    
    Returns:
        Tuple of (devices_list, error_response)
        If successful: (devices_list, None)
        If error: (None, error_response_dict)
    """
    try:
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(table_name)
        
        # Assuming there's a GSI on organization_id
        response = table.scan(
            FilterExpression='organization_id = :org_id',
            ExpressionAttributeValues={':org_id': org_id}
        )
        
        return response.get('Items', []), None
        
    except Exception as e:
        print(f"Error getting devices by organization ID: {str(e)}")
        return None, {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Internal server error'
            })
        }


def update_device_in_db(device_id: str, update_data: Dict[str, Any], table_name: str) -> Optional[Dict[str, Any]]:
    """
    Update a device in DynamoDB.
    
    Returns:
        None if successful, error response dict if failed
    """
    try:
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(table_name)
        
        # Build update expression
        update_expression = "SET "
        expression_attribute_values = {}
        expression_attribute_names = {}
        
        for key, value in update_data.items():
            if key not in ['id']:  # Don't allow updating the ID
                attr_name = f"#{key}"
                attr_value = f":{key}"
                update_expression += f"{attr_name} = {attr_value}, "
                expression_attribute_names[attr_name] = key
                expression_attribute_values[attr_value] = value
        
        # Remove trailing comma and space
        update_expression = update_expression.rstrip(', ')
        
        # Add last_updated timestamp
        update_expression += ", #last_updated = :last_updated"
        expression_attribute_names['#last_updated'] = 'last_updated'
        expression_attribute_values[':last_updated'] = datetime.now().isoformat()
        
        response = table.update_item(
            Key={'id': device_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values,
            ConditionExpression='attribute_exists(id)',
            ReturnValues='ALL_NEW'
        )
        
        return None
        
    except Exception as e:
        print(f"Error updating device: {str(e)}")
        if 'ConditionalCheckFailedException' in str(e):
            return {
                'statusCode': 404,
                'body': json.dumps({
                    'error': 'Device not found'
                })
            }
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Internal server error'
            })
        }


def prepare_update_data(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepare update data by parsing arrays and converting storage values.
    
    Returns:
        Dictionary with processed update data
    """
    update_data = {}
    
    # Copy basic fields if they exist
    basic_fields = ['name', 'description', 'model', 'version', 'ip_address', 'status']
    for field in basic_fields:
        if field in body:
            update_data[field] = body[field]
    
    # Parse array fields
    arrays = parse_array_fields(body)
    for key, value in arrays.items():
        if key in body:  # Only include if it was in the original body
            update_data[key] = value
    
    # Convert storage values
    storage = convert_storage_values(body)
    for key, value in storage.items():
        if key in body and value is not None:  # Only include if it was in the original body
            update_data[key] = value
    
    return update_data


def create_devices_list_response(devices: list) -> Dict[str, Any]:
    """
    Create a successful response for devices list.
    
    Returns:
        Success response dictionary with devices list
    """
    # Format devices for response
    formatted_devices = []
    for device in devices:
        formatted_device = format_response_device(device)
        formatted_devices.append(formatted_device)
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'devices': formatted_devices,
            'count': len(formatted_devices)
        })
    }


def create_device_response(device: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a successful response for single device.
    
    Returns:
        Success response dictionary with device data
    """
    formatted_device = format_response_device(device)
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'device': formatted_device
        })
    }
