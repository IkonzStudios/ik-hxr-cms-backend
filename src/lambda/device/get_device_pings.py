import json
import os
import re
from typing import Dict, Any, List, Optional, Tuple

from utils.helpers import (
    get_device_by_id_from_db,
    create_error_response,
    get_cors_headers,
)
from utils.rbac import check_view_permission_with_org


# ISO date pattern (YYYY-MM-DD)
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def get_device_pings_from_db(
    device_id: str,
    table_name: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Query device_pings table for a device, optionally filtered by date range.

    Returns:
        Tuple of (items, error_response). On success error_response is None.
    """
    try:
        import boto3
        from boto3.dynamodb.conditions import Key

        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)

        if start_date is not None and end_date is not None:
            key_condition = Key("device_id").eq(device_id) & Key("date").between(
                start_date, end_date
            )
        else:
            key_condition = Key("device_id").eq(device_id)

        response = table.query(KeyConditionExpression=key_condition)
        items = response.get("Items", [])

        # Handle pagination if needed
        while "LastEvaluatedKey" in response:
            response = table.query(
                KeyConditionExpression=key_condition,
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            items.extend(response.get("Items", []))

        return items, None
    except Exception as e:
        print(f"Error querying device pings: {str(e)}")
        return [], {
            "statusCode": 500,
            "headers": get_cors_headers(),
            "body": json.dumps({"error": "Failed to fetch device pings"}),
        }


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    GET /device/pings?device_id=<id>&start=<YYYY-MM-DD>&end=<YYYY-MM-DD>

    - device_id: required
    - start: optional, inclusive start date (ISO date)
    - end: optional, inclusive end date (ISO date). If start/end provided, both must be present.
    """
    try:
        if event.get("httpMethod") == "OPTIONS":
            return {
                "statusCode": 200,
                "headers": get_cors_headers(),
                "body": "",
            }

        devices_table_name = os.environ.get("DEVICES_TABLE_NAME")
        device_pings_table_name = os.environ.get("DEVICE_PINGS_TABLE_NAME")
        if not devices_table_name:
            return create_error_response(500, "DEVICES_TABLE_NAME is not configured")
        if not device_pings_table_name:
            return create_error_response(500, "DEVICE_PINGS_TABLE_NAME is not configured")

        params = event.get("queryStringParameters") or {}
        device_id = (params.get("device_id") or "").strip()
        start = (params.get("start") or "").strip()
        end = (params.get("end") or "").strip()

        if not device_id:
            return create_error_response(400, "device_id is required")

        if start or end:
            if not start or not end:
                return create_error_response(
                    400, "start and end must both be provided when filtering by date"
                )
            if not DATE_PATTERN.match(start) or not DATE_PATTERN.match(end):
                return create_error_response(
                    400, "start and end must be ISO dates (YYYY-MM-DD)"
                )
            if start > end:
                return create_error_response(400, "start must be before or equal to end")

        # Resolve device and RBAC
        device, get_error = get_device_by_id_from_db(device_id, devices_table_name)
        if get_error:
            return get_error

        rbac_error, user_info = check_view_permission_with_org(
            event, "device", device["organization_id"]
        )
        if rbac_error:
            return rbac_error

        start_date = start if start else None
        end_date = end if end else None
        items, query_error = get_device_pings_from_db(
            device_id,
            device_pings_table_name,
            start_date=start_date,
            end_date=end_date,
        )
        if query_error:
            return query_error

        return {
            "statusCode": 200,
            "headers": get_cors_headers(),
            "body": json.dumps({"pings": items}),
        }
    except Exception as e:
        print(f"Error in get_device_pings: {str(e)}")
        return create_error_response(500, "Internal server error")
