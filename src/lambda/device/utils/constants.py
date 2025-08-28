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
    "contents_initiated",
    "contents_downloading", 
    "contents_downloaded",
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

# HTTP Status codes and messages
HTTP_STATUS_CODES = {
    200: "Success",
    201: "Created successfully",
    207: "Multi-status: partial success",
    400: "Bad request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not found",
    409: "Conflict - resource already exists",
    422: "Unprocessable entity - validation error",
    500: "Internal server error",
    502: "Bad gateway - external service error",
    503: "Service unavailable",
    504: "Gateway timeout",
}

# Specific error messages for device operations
DEVICE_ERROR_MESSAGES = {
    "DEVICE_ID_REQUIRED": "Device ID is required",
    "DEVICE_NOT_FOUND": "Device not found",
    "DEVICE_ALREADY_EXISTS": "Device with this ID already exists",
    "INVALID_JSON": "Invalid JSON in request body",
    "INVALID_REQUEST_BODY": "Request body must be a JSON object",
    "EMPTY_REQUEST_BODY": "Request body cannot be empty",
    "NO_VALID_FIELDS": "No valid fields to update",
    "MISSING_ENVIRONMENT_VAR": "Required environment variable not set",
    "PERMISSION_DENIED": "Insufficient permissions for this operation",
    "CONTENT_NOT_FOUND": "Content not found",
    "PLAYLIST_NOT_FOUND": "Playlist not found",
    "APPLICATION_NOT_FOUND": "Application not found",
    "INVALID_CONTENT_IDS": "Content IDs must be a list of strings",
    "INVALID_PLAYLIST_IDS": "Playlist IDs must be a list of strings",
    "INVALID_APPLICATION_IDS": "Application IDs must be a list of strings",
    "IOT_API_ERROR": "Failed to communicate with IoT service",
    "IOT_CONFIG_FAILED": "Device configuration failed",
    "BRIGHTNESS_RANGE_ERROR": "Brightness must be a number between 0 and 100",
    "VOLUME_RANGE_ERROR": "Volume must be a number between 0 and 100",
    "SIGNAL_STRENGTH_RANGE_ERROR": "Signal strength must be a number between 0 and 100",
    "WIFI_SSID_REQUIRED": "WiFi SSID is required",
    "WIFI_SIGNAL_STRENGTH_REQUIRED": "WiFi signal strength is required",
    "INVALID_COMMAND": "Command must be a non-empty string",
    "ASSIGNMENT_FAILED": "Content/Playlist/Application assignment failed",
    "REMOVAL_NOT_IMPLEMENTED": "Removal operation not yet implemented",
}

# Success messages for device operations
DEVICE_SUCCESS_MESSAGES = {
    "CONTENT_ASSIGNED": "Content assigned to device successfully",
    "PLAYLIST_ASSIGNED": "Playlist assigned to device successfully",
    "APPLICATION_ASSIGNED": "Application assigned to device successfully",
    "CONTENT_REMOVED": "Content removed from device successfully",
    "PLAYLIST_REMOVED": "Playlist removed from device successfully",
    "APPLICATION_REMOVED": "Application removed from device successfully",
    "BRIGHTNESS_CONFIGURED": "Device brightness configured successfully",
    "VOLUME_CONFIGURED": "Device volume configured successfully",
    "WIFI_CONFIGURED": "Device WiFi configured successfully",
    "COMMAND_SENT": "Command sent to device successfully",
    "DEVICE_UPDATED": "Device updated successfully",
    "DEVICE_CREATED": "Device created successfully",
}
