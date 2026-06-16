"""
IoT local-app deployment utilities for device management.

Sends a `deploy_local_app` command to a device so the on-device superapp can
download the application build (zip) and media assets and run it locally.
"""

import json
import os
import re
import requests
import traceback
from typing import Dict, Any, List, Tuple, Optional
import boto3

from utils.helpers import get_iot_url_for_device


# Default port the local app is served on by the device superapp.
DEFAULT_LOCAL_APP_PORT = 3001

# Application type that is deployed as a local app on the device.
LOCAL_APP_TYPE = "SWA"


def slugify_app_id(name: str) -> str:
    """
    Convert an application name into a filesystem-safe app_id slug.

    e.g. "SBI" -> "sbi", "My App" -> "my_app". The device uses this as the
    local_apps/<app_id>/ directory name.
    """
    slug = re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")
    return slug


def format_version(version: str) -> str:
    """
    Convert a dotted version to the underscore form the device expects.

    e.g. "1.0.0" -> "1_0_0".
    """
    return (version or "").replace(".", "_")


def deploy_local_app_to_device_utility(
    device_id: str,
    application_ids: List[str],
    applications_table_name: str,
    content_bucket_name: str,
    devices_table_name: str = None,
) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Deploy SWA (local) applications to a device via the external IoT app-assign API.

    Looks up each application in DynamoDB and, for every SWA app that has a build
    zip, sends a `deploy_local_app` command to the device.

    Args:
        device_id: The device ID (used as the IoT thingName)
        application_ids: Application IDs being assigned
        applications_table_name: DynamoDB table name for applications
        content_bucket_name: S3 bucket name holding the app zip + assets
        devices_table_name: DynamoDB table name for devices (optional)

    Returns:
        Tuple of (success, error_message, result)
        result contains the per-app deploy outcomes and a deployed count.
    """
    try:
        if not devices_table_name:
            devices_table_name = os.environ.get("DEVICES_TABLE_NAME")

        if not devices_table_name:
            return False, "DEVICES_TABLE_NAME environment variable not set", None

        if not device_id or not isinstance(device_id, str):
            return False, "device_id must be a non-empty string", None

        if not application_ids or not isinstance(application_ids, list):
            return False, "application_ids must be a non-empty list", None

        if not applications_table_name:
            return False, "APPLICATIONS_TABLE_NAME environment variable not set", None

        if not content_bucket_name:
            return False, "CONTENT_BUCKET_NAME environment variable not set", None

        dynamodb = boto3.resource("dynamodb")

        # Check device exists and resolve the region-specific IoT URL
        devices_table = dynamodb.Table(devices_table_name)
        device_response = devices_table.get_item(Key={"id": device_id})
        if "Item" not in device_response:
            return False, "Device not found", None

        device_item = device_response["Item"]
        iot_app_assign_url = get_iot_url_for_device(
            device_item, "IOT_APP_ASSIGN_API_URL", "IOT_APP_ASSIGN_API_URL_OLD"
        )
        if not iot_app_assign_url:
            return False, "IOT_APP_ASSIGN_API_URL environment variable not set", None

        applications_table = dynamodb.Table(applications_table_name)

        deploy_results: List[Dict[str, Any]] = []
        deployed_count = 0

        for application_id in application_ids:
            try:
                app_response = applications_table.get_item(Key={"id": application_id})
            except Exception as e:
                print(f"Error retrieving application {application_id}: {str(e)}")
                continue

            if "Item" not in app_response:
                print(f"Warning: Application {application_id} not found in database")
                continue

            application = app_response["Item"]

            # Only SWA applications are deployed as local apps
            if application.get("type") != LOCAL_APP_TYPE:
                continue

            zip_key = application.get("zip_url")
            if not zip_key:
                print(
                    f"Warning: SWA application {application_id} has no zip_url; skipping deploy"
                )
                deploy_results.append(
                    {
                        "application_id": application_id,
                        "success": False,
                        "error": "Application has no build zip (zip_url)",
                    }
                )
                continue

            video_urls = application.get("video_urls", []) or []
            if isinstance(video_urls, str):
                video_urls = json.loads(video_urls) if video_urls else []

            iot_payload = {
                "action": "deploy_local_app",
                "thingName": device_id,
                "payload": {
                    "app_id": slugify_app_id(application.get("name", "")),
                    "version": format_version(application.get("version", "")),
                    "port": DEFAULT_LOCAL_APP_PORT,
                    "s3_bucket": content_bucket_name,
                    "s3_zip_key": zip_key,
                    "assets": list(video_urls),
                },
            }

            print(f"Deploying local app {application_id} to device {device_id}")
            print(f"IoT API Payload: {json.dumps(iot_payload, indent=2)}")

            try:
                response = requests.post(
                    iot_app_assign_url,
                    json=iot_payload,
                    headers={"Content-Type": "application/json"},
                    timeout=30,
                )
            except requests.exceptions.RequestException as e:
                error_msg = f"Failed to communicate with IoT API: {str(e)}"
                print(error_msg)
                deploy_results.append(
                    {
                        "application_id": application_id,
                        "success": False,
                        "error": error_msg,
                    }
                )
                continue

            print(f"IoT API Response Status: {response.status_code}")
            print(f"IoT API Response: {response.text}")

            if response.status_code == 200:
                deployed_count += 1
                deploy_results.append(
                    {
                        "application_id": application_id,
                        "success": True,
                        "response": response.json() if response.text else {},
                    }
                )
            else:
                deploy_results.append(
                    {
                        "application_id": application_id,
                        "success": False,
                        "error": f"IoT API returned status {response.status_code}: {response.text}",
                    }
                )

        # Overall success only if every attempted SWA deploy succeeded
        all_succeeded = all(r.get("success") for r in deploy_results) if deploy_results else True
        result = {
            "deployed_count": deployed_count,
            "results": deploy_results,
        }

        if not all_succeeded:
            failed = [r for r in deploy_results if not r.get("success")]
            error_msg = "; ".join(
                f"{r['application_id']}: {r.get('error')}" for r in failed
            )
            return False, error_msg, result

        return True, None, result

    except Exception as e:
        error_msg = f"Error deploying local app to device: {str(e)}"
        print(error_msg)
        print(f"Traceback: {traceback.format_exc()}")
        return False, error_msg, None
