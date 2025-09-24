import json
import os
import boto3
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Tuple, Optional
from .constants import REQUIRED_DEVICE_FIELDS


def get_cors_headers() -> Dict[str, str]:
    """
    Get standard CORS headers for all responses.

    Returns:
        Dictionary with CORS headers
    """
    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token,X-Requested-With,Origin,Accept,Cache-Control,Pragma,If-Modified-Since,X-Forwarded-For,X-Forwarded-Proto,X-Forwarded-Port",
        "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS,PATCH,HEAD",
        "Access-Control-Max-Age": "86400",
    }


def parse_request_body(
    event: Dict[str, Any]
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Parse the request body from the event.

    Returns:
        Tuple of (parsed_body, error_response)
        If successful: (body_dict, None)
        If error: (None, error_response_dict)
    """
    body = None

    if "body" in event:
        if isinstance(event["body"], str):
            try:
                body = json.loads(event["body"])
            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e}")
                return None, {
                    "statusCode": 400,
                    "headers": get_cors_headers(),
                    "body": json.dumps({"error": "Invalid JSON in request body"}),
                }
        elif isinstance(event["body"], dict):
            body = event["body"]
        else:
            print(f"Unexpected body type: {type(event['body'])}")
            return None, {
                "statusCode": 400,
                "headers": get_cors_headers(),
                "body": json.dumps({"error": "Invalid request body format"}),
            }

    # Ensure body is a dictionary
    if not isinstance(body, dict):
        print(f"Body is not a dictionary: {type(body)}")
        return None, {
            "statusCode": 400,
            "headers": get_cors_headers(),
            "body": json.dumps({"error": "Request body must be a JSON object"}),
        }

    return body, None


def validate_required_fields(body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Validate that all required fields are present in the request body.

    Returns:
        None if validation passes, error response dict if validation fails
    """
    for field in REQUIRED_DEVICE_FIELDS:
        if not body.get(field["column_name"]):
            return {
                "statusCode": 400,
                "headers": get_cors_headers(),
                "body": json.dumps({"error": f'{field["name"]} is required'}),
            }
    return None


def parse_array_fields(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse stringified array fields (playlists, applications, contents) from the body.

    Returns:
        Dictionary with parsed array values
    """
    result = {}

    for field_name in ["playlists", "applications", "contents_initiated"]:
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

    storage_left = body.get("storage_left")
    if storage_left is not None:
        result["storage_left"] = Decimal(str(storage_left))
    else:
        result["storage_left"] = None

    storage_consumed = body.get("storage_consumed")
    if storage_consumed is not None:
        result["storage_consumed"] = Decimal(str(storage_consumed))
    else:
        result["storage_consumed"] = None

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
    # device_id = str(uuid.uuid4())
    current_time = datetime.now().isoformat()

    # Create device data dictionary
    device_data = {
        "id": body["id"],
        "name": body["name"],
        "organization_id": body["organization_id"],
        "description": body.get("description"),
        "model": body.get("model"),
        "version": body.get("version"),
        "ip_address": body.get("ip_address"),
        "playlists": arrays["playlists"],
        "applications": arrays["applications"],
        "contents_initiated": [],
        "contents_downloading": [],
        "contents_downloaded": [],
        "contents_failed": [],
        "base_content": "",
        "status": body.get("status", "active"),
        "is_deleted": body.get("is_deleted", False),
        "last_seen": current_time,
        "last_updated": current_time,
        "storage_left": storage["storage_left"],
        "storage_consumed": storage["storage_consumed"],
        "created_at": current_time,
        "updated_at": current_time,
        "created_by": body.get("created_by", ""),
        "updated_by": body.get("updated_by", ""),
    }

    return device_data


def save_device_to_db(
    device_data: Dict[str, Any], table_name: str
) -> Optional[Dict[str, Any]]:
    """
    Save device data to DynamoDB.

    Returns:
        None if successful, error response dict if failed
    """
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)

        table.put_item(Item=device_data, ConditionExpression="attribute_not_exists(id)")
        return None

    except Exception as e:
        print(f"Error creating device: {str(e)}")
        print(f"Error type: {type(e)}")
        print(f"Error message: {str(e)}")
        return {
            "statusCode": 409,
            "headers": get_cors_headers(),
            "body": json.dumps({"error": "Device with this ID already exists"}),
        }


def format_response_device(device_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format device data for JSON response by converting Decimal to float.

    Returns:
        Device data with Decimal values converted to float
    """
    response_device = device_data.copy()

    if response_device.get("storage_left") is not None:
        response_device["storage_left"] = float(response_device["storage_left"])
    if response_device.get("storage_consumed") is not None:
        response_device["storage_consumed"] = float(response_device["storage_consumed"])

    return response_device


def create_success_response(device_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a successful response for device creation.

    Returns:
        Success response dictionary
    """
    response_device = format_response_device(device_data)

    return {
        "statusCode": 201,
        "headers": get_cors_headers(),
        "body": json.dumps(
            {
                "message": "Device created successfully",
                "device_id": device_data["id"],
                "device": response_device,
            }
        ),
    }


def create_error_response(status_code: int, error_message: str) -> Dict[str, Any]:
    """
    Create an error response.

    Returns:
        Error response dictionary
    """
    return {
        "statusCode": status_code,
        "headers": get_cors_headers(),
        "body": json.dumps({"error": error_message}),
    }


def get_device_by_id_from_db(
    device_id: str, table_name: str
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Get a device by ID from DynamoDB.

    Returns:
        Tuple of (device_data, error_response)
        If successful: (device_dict, None)
        If error: (None, error_response_dict)
    """
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)

        response = table.get_item(Key={"id": device_id})

        if "Item" not in response:
            return None, {
                "statusCode": 404,
                "headers": get_cors_headers(),
                "body": json.dumps({"error": "Device not found"}),
            }

        return response["Item"], None

    except Exception as e:
        print(f"Error getting device: {str(e)}")
        return None, {
            "statusCode": 500,
            "headers": get_cors_headers(),
            "body": json.dumps({"error": "Internal server error"}),
        }


def get_devices_by_org_id_from_db(
    org_id: str, table_name: str
) -> Tuple[Optional[list], Optional[Dict[str, Any]]]:
    """
    Get all devices by organization ID from DynamoDB.

    Returns:
        Tuple of (devices_list, error_response)
        If successful: (devices_list, None)
        If error: (None, error_response_dict)
    """
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)

        # Assuming there's a GSI on organization_id
        response = table.scan(
            FilterExpression="organization_id = :org_id",
            ExpressionAttributeValues={":org_id": org_id},
        )

        return response.get("Items", []), None

    except Exception as e:
        print(f"Error getting devices by organization ID: {str(e)}")
        return None, {
            "statusCode": 500,
            "headers": get_cors_headers(),
            "body": json.dumps({"error": "Internal server error"}),
        }


def update_device_in_db(
    device_id: str, update_data: Dict[str, Any], table_name: str
) -> Optional[Dict[str, Any]]:
    """
    Update a device in DynamoDB.

    Returns:
        None if successful, error response dict if failed
    """
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)

        # Build update expression
        update_expression = "SET "
        expression_attribute_values = {}
        expression_attribute_names = {}

        for key, value in update_data.items():
            if key not in ["id"]:  # Don't allow updating the ID
                attr_name = f"#{key}"
                attr_value = f":{key}"
                update_expression += f"{attr_name} = {attr_value}, "
                expression_attribute_names[attr_name] = key
                expression_attribute_values[attr_value] = value

        # Remove trailing comma and space
        update_expression = update_expression.rstrip(", ")

        # Add last_updated timestamp
        update_expression += ", #last_updated = :last_updated"
        expression_attribute_names["#last_updated"] = "last_updated"
        expression_attribute_values[":last_updated"] = datetime.now().isoformat()

        table.update_item(
            Key={"id": device_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values,
            ConditionExpression="attribute_exists(id)",
            ReturnValues="ALL_NEW",
        )

        return None

    except Exception as e:
        print(f"Error updating device: {str(e)}")
        if "ConditionalCheckFailedException" in str(e):
            return {
                "statusCode": 404,
                "headers": get_cors_headers(),
                "body": json.dumps({"error": "Device not found"}),
            }
        return {
            "statusCode": 500,
            "headers": get_cors_headers(),
            "body": json.dumps({"error": "Internal server error"}),
        }


def prepare_update_data(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepare update data by parsing arrays and converting storage values.

    Returns:
        Dictionary with processed update data
    """
    update_data = {}

    # Copy basic fields if they exist
    basic_fields = ["name", "description", "model", "version", "ip_address", "status"]
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
        if (
            key in body and value is not None
        ):  # Only include if it was in the original body
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
        "statusCode": 200,
        "headers": get_cors_headers(),
        "body": json.dumps(
            {"devices": formatted_devices, "count": len(formatted_devices)}
        ),
    }


def create_device_response(device: Dict[str, Any], iot_assignment_result: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Create a successful response for single device.

    Args:
        device: Device data dictionary
        iot_assignment_result: Optional IoT assignment result for device updates

    Returns:
        Success response dictionary with device data and optional IoT results
    """
    formatted_device = format_response_device(device)
    
    # Prepare response body
    response_body = {"device": formatted_device}
    
    # Add IoT assignment result if provided
    if iot_assignment_result:
        response_body["iot_content_assignment"] = iot_assignment_result
    
    # Determine status code and message based on IoT result
    if iot_assignment_result and not iot_assignment_result.get("success", True):
        # Device update succeeded but IoT assignment failed
        status_code = 207  # Multi-status: partial success
        response_body["message"] = "Device updated successfully but IoT content assignment failed"
        response_body["warning"] = "Content assignment to IoT device failed"
    else:
        # Normal success response
        status_code = 200
        if iot_assignment_result and iot_assignment_result.get("success"):
            response_body["message"] = "Device updated successfully with IoT content assignment"
        # Note: No message for regular device operations to maintain backward compatibility

    return {
        "statusCode": status_code,
        "headers": get_cors_headers(),
        "body": json.dumps(response_body),
    }


def get_items_by_ids(table_name: str, item_ids: list) -> list:
    """
    Get multiple items by their IDs from a DynamoDB table.
    
    Args:
        table_name: Name of the DynamoDB table
        item_ids: List of item IDs to fetch
        
    Returns:
        List of items found (may be fewer than requested if some IDs don't exist)
    """
    if not item_ids:
        return []
    
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)
        
        items = []
        # DynamoDB batch_get_item has a limit of 100 items
        for i in range(0, len(item_ids), 100):
            batch_ids = item_ids[i:i+100]
            
            response = dynamodb.batch_get_item(
                RequestItems={
                    table_name: {
                        'Keys': [{'id': item_id} for item_id in batch_ids]
                    }
                }
            )
            
            if table_name in response.get('Responses', {}):
                items.extend(response['Responses'][table_name])
        
        return items
    except Exception as e:
        print(f"Error getting items from {table_name}: {str(e)}")
        return []


def enrich_device_with_related_data(device: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enrich a device object with full data for contents, playlists, and applications.
    
    Args:
        device: Device object with ID references
        
    Returns:
        Device object with full related data
    """
    enriched_device = device.copy()
    
    try:
        # Get table names from environment
        contents_table_name = os.environ.get("CONTENTS_TABLE_NAME")
        playlists_table_name = os.environ.get("PLAYLISTS_TABLE_NAME")
        applications_table_name = os.environ.get("APPLICATIONS_TABLE_NAME")
        
        # Parse and enrich content status arrays
        content_status_fields = ["contents_initiated", "contents_downloading", "contents_downloaded"]
        for field in content_status_fields:
            content_ids = device.get(field, [])
            if isinstance(content_ids, str):
                content_ids = json.loads(content_ids) if content_ids else []
            
            if content_ids and contents_table_name:
                contents = get_items_by_ids(contents_table_name, content_ids)
                enriched_device[field] = [format_response_item(content) for content in contents]
            else:
                enriched_device[field] = []
        
        # Parse and enrich playlists
        playlist_ids = device.get("playlists", [])
        if isinstance(playlist_ids, str):
            playlist_ids = json.loads(playlist_ids) if playlist_ids else []
        
        if playlist_ids and playlists_table_name:
            playlists = get_items_by_ids(playlists_table_name, playlist_ids)
            enriched_device["playlists"] = [format_response_item(playlist) for playlist in playlists]
        else:
            enriched_device["playlists"] = []
        
        # Parse and enrich applications
        application_ids = device.get("applications", [])
        if isinstance(application_ids, str):
            application_ids = json.loads(application_ids) if application_ids else []
        
        if application_ids and applications_table_name:
            applications = get_items_by_ids(applications_table_name, application_ids)
            enriched_device["applications"] = [format_response_item(app) for app in applications]
        else:
            enriched_device["applications"] = []
            
    except Exception as e:
        print(f"Error enriching device data: {str(e)}")
        # Return device with empty arrays if enrichment fails
        enriched_device["contents_initiated"] = []
        enriched_device["contents_downloading"] = []
        enriched_device["contents_downloaded"] = []
        enriched_device["playlists"] = []
        enriched_device["applications"] = []
    
    return enriched_device


def format_response_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format an item for JSON response by converting Decimal to float and handling special types.
    
    Args:
        item: Item data from DynamoDB
        
    Returns:
        Item data formatted for JSON response
    """
    formatted_item = {}
    
    for key, value in item.items():
        if isinstance(value, Decimal):
            formatted_item[key] = float(value)
        elif isinstance(value, str) and key in ["contents_initiated", "contents_downloading", "contents_downloaded", "playlists", "applications"]:
            # Parse JSON strings for nested arrays
            try:
                formatted_item[key] = json.loads(value) if value else []
            except json.JSONDecodeError:
                formatted_item[key] = []
        else:
            formatted_item[key] = value
    
    return formatted_item


def create_enriched_device_response(device: Dict[str, Any], iot_assignment_result: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Create a device response with enriched related data.
    
    Args:
        device: Device data dictionary
        iot_assignment_result: Optional IoT assignment result
        
    Returns:
        Success response dictionary with enriched device data
    """
    # First format the device for basic response
    formatted_device = format_response_device(device)
    
    # Then enrich with related data
    # TODO: Uncomment this later
    # enriched_device = enrich_device_with_related_data(formatted_device)
    enriched_device = formatted_device.copy()
    
    # Prepare response body
    response_body = {"device": enriched_device}
    
    # Add IoT assignment result if provided
    if iot_assignment_result:
        response_body["iot_content_assignment"] = iot_assignment_result
    
    # Determine status code and message based on IoT result
    if iot_assignment_result and not iot_assignment_result.get("success", True):
        # Device update succeeded but IoT assignment failed
        status_code = 207  # Multi-status: partial success
        response_body["message"] = "Device updated successfully but IoT content assignment failed"
        response_body["warning"] = "Content assignment to IoT device failed"
    else:
        # Normal success response
        status_code = 200
        if iot_assignment_result and iot_assignment_result.get("success"):
            response_body["message"] = "Device updated successfully with IoT content assignment"
        # Note: No message for regular device operations to maintain backward compatibility

    return {
        "statusCode": status_code,
        "headers": get_cors_headers(),
        "body": json.dumps(response_body),
    }


def create_enriched_devices_list_response(devices: list) -> Dict[str, Any]:
    """
    Create a successful response for enriched devices list.

    Args:
        devices: List of device dictionaries
        
    Returns:
        Success response dictionary with enriched devices list
    """
    # Format and enrich devices for response
    enriched_devices = []
    for device in devices:
        formatted_device = format_response_device(device)
        enriched_device = enrich_device_with_related_data(formatted_device)
        enriched_devices.append(enriched_device)

    return {
        "statusCode": 200,
        "headers": get_cors_headers(),
        "body": json.dumps(
            {"devices": enriched_devices, "count": len(enriched_devices)}
        ),
    }
