import json
import boto3
import uuid
import requests
from datetime import datetime
from typing import Dict, Any, Tuple, Optional, List
from .constants import REQUIRED_SCHEDULE_FIELDS
import time


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
    for field in REQUIRED_SCHEDULE_FIELDS:
        if not body.get(field["column_name"]):
            return {
                "statusCode": 400,
                "headers": get_cors_headers(),
                "body": json.dumps({"error": f'{field["name"]} is required'}),
            }
    return None


def validate_datetime_format(
    datetime_str: str, field_name: str
) -> Optional[Dict[str, Any]]:
    """
    Validate datetime format (ISO 8601).

    Returns:
        None if valid, error response dict if invalid
    """
    try:
        datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
        return None
    except ValueError:
        return {
            "statusCode": 400,
            "headers": get_cors_headers(),
            "body": json.dumps(
                {
                    "error": f"{field_name} must be in ISO 8601 format (e.g., '2024-01-15T10:30:00Z')"
                }
            ),
        }


def validate_schedule_times(body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Validate that start_at is before end_at.

    Returns:
        None if valid, error response dict if invalid
    """
    try:
        start_at = datetime.fromisoformat(body["start_at"].replace("Z", "+00:00"))
        end_at = datetime.fromisoformat(body["end_at"].replace("Z", "+00:00"))

        if start_at >= end_at:
            return {
                "statusCode": 400,
                "headers": get_cors_headers(),
                "body": json.dumps({"error": "start_at must be before end_at"}),
            }
        return None
    except ValueError:
        return {
            "statusCode": 400,
            "headers": get_cors_headers(),
            "body": json.dumps({"error": "Invalid datetime format"}),
        }


def parse_array_fields(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse stringified array fields (assigned_to, contents, playlists, applications) from the body.

    Returns:
        Dictionary with parsed array values
    """
    result = {}

    for field_name in ["assigned_to", "contents", "playlists", "applications"]:
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


def create_schedule_data(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create the schedule data dictionary from the request body.

    Returns:
        Complete schedule data dictionary ready for DynamoDB
    """
    # Parse array fields
    arrays = parse_array_fields(body)

    # Generate schedule ID and timestamps
    schedule_id = str(uuid.uuid4())
    current_time = datetime.now().isoformat()

    # Create schedule data dictionary
    schedule_data = {
        "id": schedule_id,
        "title": body.get("title", ""),
        "start_at": body["start_at"],
        "end_at": body["end_at"],
        "loop": body.get("loop", False),
        "is_active": body.get("is_active", True),
        "is_deleted": body.get("is_deleted", False),
        "assigned_to": arrays["assigned_to"],
        "contents": arrays["contents"],
        "playlists": arrays["playlists"],
        "applications": arrays["applications"],
        "organization_id": body["organization_id"],
        "created_at": current_time,
        "updated_at": current_time,
        "created_by": body.get("created_by", ""),
        "updated_by": body.get("updated_by", ""),
    }

    return schedule_data


def save_schedule_to_db(
    schedule_data: Dict[str, Any], table_name: str, device_table_name: str
) -> Optional[Dict[str, Any]]:
    """
    Save schedule data to DynamoDB.

    Returns:
        None if successful, error response dict if failed
    """
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)

        table.put_item(
            Item=schedule_data, ConditionExpression="attribute_not_exists(id)"
        )
        device_table = dynamodb.Table(device_table_name)
        
        # Use batch_get_item correctly - it's called on the DynamoDB resource, not the table
        response = dynamodb.batch_get_item(
            RequestItems={
                device_table_name: {
                    'Keys': [{"id": device_id} for device_id in schedule_data["assigned_to"]]
                }
            }
        )
        
        # Process the response correctly
        devices_data = response.get('Responses', {}).get(device_table_name, [])
        
        print(f"Devices data: {devices_data}")
        for device_data in devices_data:
            schedules = json.loads(device_data.get("schedules", "[]"))
            schedules.append(schedule_data["id"])
            print(f"Schedules: {schedules}")
            device_table.update_item(
                Key={"id": device_data["id"]},
                UpdateExpression="SET schedules = :schedules",
                ExpressionAttributeValues={":schedules": schedules}
            )
        
        # Check for unprocessed keys (devices that weren't found)
        unprocessed_keys = response.get('UnprocessedKeys', {})
        if unprocessed_keys:
            print(f"Some devices were not found: {unprocessed_keys}")
        
        return None

    except Exception as e:
        print(f"Error creating schedule: {str(e)}")
        print(f"Error type: {type(e)}")
        print(f"Error message: {str(e)}")
        return {
            "statusCode": 409,
            "headers": get_cors_headers(),
            "body": json.dumps({"error": "Schedule with this ID already exists"}),
        }


def create_success_response(schedule_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a success response with schedule data.

    Returns:
        Success response dictionary
    """
    return {
        "statusCode": 201,
        "headers": get_cors_headers(),
        "body": json.dumps(
            {"message": "Schedule created successfully", "data": schedule_data}
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


def get_schedule_by_id_from_db(
    schedule_id: str, table_name: str
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Get schedule by ID from DynamoDB.

    Returns:
        Tuple of (schedule_data, error_response)
        If successful: (schedule_dict, None)
        If error: (None, error_response_dict)
    """
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)

        response = table.get_item(Key={"id": schedule_id})

        if "Item" not in response:
            return None, {
                "statusCode": 404,
                "headers": get_cors_headers(),
                "body": json.dumps({"error": "Schedule not found"}),
            }

        return response["Item"], None

    except Exception as e:
        print(f"Error getting schedule: {str(e)}")
        return None, {
            "statusCode": 500,
            "headers": get_cors_headers(),
            "body": json.dumps({"error": "Internal server error"}),
        }


def get_schedules_by_org_id_from_db(
    org_id: str, table_name: str
) -> Tuple[Optional[list], Optional[Dict[str, Any]]]:
    """
    Get all schedules by organization ID from DynamoDB.

    Returns:
        Tuple of (schedules_list, error_response)
        If successful: (schedules_list, None)
        If error: (None, error_response_dict)
    """
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)

        response = table.scan(
            FilterExpression="organization_id = :org_id",
            ExpressionAttributeValues={":org_id": org_id},
        )

        return response.get("Items", []), None

    except Exception as e:
        print(f"Error getting schedules by organization ID: {str(e)}")
        return None, {
            "statusCode": 500,
            "headers": get_cors_headers(),
            "body": json.dumps({"error": "Internal server error"}),
        }


def update_schedule_in_db(
    schedule_id: str, update_data: Dict[str, Any], table_name: str
) -> Optional[Dict[str, Any]]:
    """
    Update schedule in DynamoDB.

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
            if key == "updated_at":
                update_expression += "updated_at = :updated_at, "
                expression_attribute_values[":updated_at"] = value
            else:
                # Use attribute names to handle reserved words
                attr_name = f"#{key}"
                attr_value = f":{key}"
                expression_attribute_names[attr_name] = key
                expression_attribute_values[attr_value] = value
                update_expression += f"{attr_name} = {attr_value}, "

        # Remove trailing comma and space
        update_expression = update_expression.rstrip(", ")

        # Always update the updated_at timestamp
        current_time = datetime.now().isoformat()
        update_expression += ", updated_at = :current_time"
        expression_attribute_values[":current_time"] = current_time

        table.update_item(
            Key={"id": schedule_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values,
            ExpressionAttributeNames=expression_attribute_names
            if expression_attribute_names
            else None,
            ConditionExpression="attribute_exists(id)",
        )

        return None

    except Exception as e:
        print(f"Error updating schedule: {str(e)}")
        if "ConditionalCheckFailedException" in str(e):
            return {
                "statusCode": 404,
                "headers": get_cors_headers(),
                "body": json.dumps({"error": "Schedule not found"}),
            }
        return {
            "statusCode": 500,
            "headers": get_cors_headers(),
            "body": json.dumps({"error": "Internal server error"}),
        }


def prepare_update_data(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepare update data from request body, filtering out invalid fields.

    Returns:
        Dictionary with valid update fields
    """
    allowed_fields = [
        "title",
        "start_at",
        "end_at",
        "loop",
        "is_active",
        "assigned_to",
        "contents",
        "playlists",
        "applications",
        "updated_by",
        "is_deleted",
    ]

    update_data = {}

    for field in allowed_fields:
        if field in body:
            if field in ["assigned_to", "contents", "playlists", "applications"]:
                # Handle array fields
                arrays = parse_array_fields({field: body[field]})
                update_data[field] = arrays[field]
            else:
                update_data[field] = body[field]

    return update_data


def create_schedules_list_response(schedules: list) -> Dict[str, Any]:
    """
    Create a response with list of schedules.

    Returns:
        Response dictionary with schedules list
    """
    return {
        "statusCode": 200,
        "headers": get_cors_headers(),
        "body": json.dumps(
            {
                "message": "Schedules retrieved successfully",
                "data": schedules,
                "count": len(schedules),
            }
        ),
    }


def create_schedule_response(schedule: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a response with single schedule data.

    Returns:
        Response dictionary with schedule data
    """
    return {
        "statusCode": 200,
        "headers": get_cors_headers(),
        "body": json.dumps(
            {"message": "Schedule retrieved successfully", "data": schedule}
        ),
    }


def get_playlist_by_id(playlist_id: str, playlists_table_name: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Get playlist by ID from DynamoDB.

    Returns:
        Tuple of (playlist_data, error_message)
        If successful: (playlist_dict, None)
        If error: (None, error_message)
    """
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(playlists_table_name)

        response = table.get_item(Key={"id": playlist_id})

        if "Item" not in response:
            return None, f"Playlist with ID {playlist_id} not found"

        return response["Item"], None

    except Exception as e:
        print(f"Error getting playlist {playlist_id}: {str(e)}")
        return None, f"Error retrieving playlist {playlist_id}: {str(e)}"


def get_content_by_id(content_id: str, contents_table_name: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Get content by ID from DynamoDB.

    Returns:
        Tuple of (content_data, error_message)
        If successful: (content_dict, None)
        If error: (None, error_message)
    """
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(contents_table_name)

        response = table.get_item(Key={"id": content_id})

        if "Item" not in response:
            return None, f"Content with ID {content_id} not found"

        return response["Item"], None

    except Exception as e:
        print(f"Error getting content {content_id}: {str(e)}")
        return None, f"Error retrieving content {content_id}: {str(e)}"


def extract_s3_info_from_url(url: str, default_bucket: str) -> Tuple[str, str]:
    """
    Extract S3 bucket and key from content URL.
    
    Args:
        url: Content URL (could be S3 path or full URL)
        default_bucket: Default S3 bucket name to use
        
    Returns:
        Tuple of (bucket_name, s3_key)
    """
    if url.startswith("contents/"):
        # URL is already in the format contents/org_id/filename
        return default_bucket, url
    elif url.startswith("s3://"):
        # URL is in format s3://bucket/key
        parts = url[5:].split("/", 1)
        if len(parts) == 2:
            return parts[0], parts[1]
        else:
            return default_bucket, parts[0]
    elif "amazonaws.com" in url:
        # URL is a full S3 URL, extract key part
        # Example: https://bucket.s3.region.amazonaws.com/contents/org_id/file.mp4
        if "/contents/" in url:
            key_part = url.split("/contents/", 1)[1]
            return default_bucket, f"contents/{key_part}"
        else:
            # Extract everything after domain
            domain_end = url.find(".amazonaws.com/")
            if domain_end != -1:
                key_part = url[domain_end + len(".amazonaws.com/"):]
                return default_bucket, key_part
    
    # Fallback: treat as S3 key with default bucket
    return default_bucket, url


def get_application_by_id(application_id: str, applications_table_name: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Get application by ID from DynamoDB.
    
    Returns:
        Tuple of (application_data, error_message)
        If successful: (application_dict, None)
        If error: (None, error_message)
    """
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(applications_table_name)

        response = table.get_item(Key={"id": application_id})

        if "Item" not in response:
            return None, f"Application with ID {application_id} not found"

        return response["Item"], None

    except Exception as e:
        print(f"Error getting application {application_id}: {str(e)}")
        return None, f"Error retrieving application {application_id}: {str(e)}"


def collect_contents_from_playlists_and_contents(
    playlists: List[str], 
    contents: List[str], 
    playlists_table_name: str, 
    contents_table_name: str,
    default_s3_bucket: str
) -> Tuple[List[Dict[str, str]], List[str]]:
    """
    Collect all content information from playlists and individual contents.
    
    Args:
        playlists: List of playlist IDs
        contents: List of content IDs
        playlists_table_name: DynamoDB table name for playlists
        contents_table_name: DynamoDB table name for contents
        default_s3_bucket: Default S3 bucket name
        
    Returns:
        Tuple of (content_list, error_messages)
        content_list: List of dicts with s3Bucket and s3Key
        error_messages: List of error messages encountered
    """
    content_list = []
    error_messages = []
    processed_content_ids = set()  # To avoid duplicates
    
    # Process playlists first (they take precedence)
    for playlist_id in playlists:
        playlist_data, error = get_playlist_by_id(playlist_id, playlists_table_name)
        if error:
            error_messages.append(f"Playlist error: {error}")
            continue
            
        # Get contents from playlist
        playlist_contents = playlist_data.get("contents", [])
        if isinstance(playlist_contents, str):
            try:
                playlist_contents = json.loads(playlist_contents)
            except json.JSONDecodeError:
                playlist_contents = []
        
        # Process each content in the playlist
        for content_id in playlist_contents:
            if content_id in processed_content_ids:
                continue  # Skip duplicates
                
            content_data, error = get_content_by_id(content_id, contents_table_name)
            if error:
                error_messages.append(f"Content error: {error}")
                continue
                
            # Extract S3 information from content URL
            content_url = content_data.get("url", "")
            if content_url:
                s3_bucket, s3_key = extract_s3_info_from_url(content_url, default_s3_bucket)
                content_list.append({
                    "s3Bucket": s3_bucket,
                    "s3Key": s3_key,
                    "id": content_id,
                    "duration": content_data.get("duration", "0"),
                })
                processed_content_ids.add(content_id)
    
    # Process individual contents
    for content_id in contents:
        if content_id in processed_content_ids:
            continue  # Skip duplicates
            
        content_data, error = get_content_by_id(content_id, contents_table_name)
        if error:
            error_messages.append(f"Content error: {error}")
            continue
            
        # Extract S3 information from content URL
        content_url = content_data.get("url", "")
        if content_url:
            s3_bucket, s3_key = extract_s3_info_from_url(content_url, default_s3_bucket)
            content_list.append({
                "s3Bucket": s3_bucket,
                "s3Key": s3_key,
                "id": content_id,
                "duration": content_data.get("duration", "0"),
            })
            processed_content_ids.add(content_id)
    
    return content_list, error_messages


def calculate_times_played(contents, time_difference, count_started=True):
    """
    Calculate how many times each content in the playlist is played 
    within a given time interval.
    
    Args:
        contents (list[int]): List of durations (seconds) of each content.
        time_difference (int): Total time interval in seconds.
        count_started (bool): 
            - True  => count if content starts within the interval
            - False => count only if content finishes within the interval

    Returns:
        list[int]: Number of times each content is played.
    """
    n = len(contents)
    result = [0] * n

    total_duration = sum(contents)
    full_loops = time_difference // total_duration
    remaining_time = time_difference % total_duration

    # Each content is played full_loops times
    for i in range(n):
        result[i] += full_loops

    # Handle remaining time
    for i in range(n):
        if count_started:
            if remaining_time > 0:   # started play counts
                result[i] += 1
                remaining_time -= contents[i]
            else:
                break
        else:
            if remaining_time >= contents[i]:  # full play fits
                result[i] += 1
                remaining_time -= contents[i]
            else:
                break

    return result


def save_playback_data(playback_data: Dict[str, Any], table_name: str) -> Optional[Dict[str, Any]]:
    """
    Save playback data to DynamoDB.

    Returns:
        None if successful, error response dict if failed
    """
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)

        table.put_item(
            Item=playback_data, ConditionExpression="attribute_not_exists(id)"
        )
        return None

    except Exception as e:
        print(f"Error creating playback: {str(e)}")
        print(f"Error type: {type(e)}")
        print(f"Error message: {str(e)}")
        return {
            "statusCode": 409,
            "headers": get_cors_headers(),
            "body": json.dumps({"error": "Playback with this ID already exists"}),
        }