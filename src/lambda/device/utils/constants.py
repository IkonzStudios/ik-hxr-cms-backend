# Required fields for device creation
REQUIRED_DEVICE_FIELDS = [
    {
        "name": "ID",
        "column_name": "id",
    },
    {
        "name": "Name",
        "column_name": "name",
    },
    {
        "name": "Organization ID",
        "column_name": "organization_id",
    },
]

# Optional fields for device creation and updates
OPTIONAL_DEVICE_FIELDS = [
    "description",
    "model",
    "version",
    "ip_address",
    "playlists",
    "applications",
    "contents",
    "status",
    "storage_left",
    "storage_consumed",
    "is_deleted",
    "created_by",
    "updated_by",
]

# Device field types for validation
DEVICE_FIELD_TYPES = {
    "id": str,  # Device ID
    "name": str,  # Device name
    "description": str,  # Device description
    "model": str,  # Device model
    "version": str,  # Device version/firmware
    "ip_address": str,  # IP address
    "status": str,  # Device status
    "is_deleted": bool,  # Soft delete flag
}

# Valid device status values
VALID_DEVICE_STATUS = [
    "active",
    "inactive",
    "offline",
    "maintenance",
]
