# Required fields for application creation
REQUIRED_APPLICATION_FIELDS = [
    {
        "name": "Name",
        "column_name": "name",
    },
    {
        "name": "Version",
        "column_name": "version",
    },
    {
        "name": "Platform",
        "column_name": "platform",
    },
    {
        "name": "Organization ID",
        "column_name": "organization_id",
    },
]

# Optional fields for application creation and updates
OPTIONAL_APPLICATION_FIELDS = [
    "logo",
    "description",
    "is_deleted",
    "created_by",
    "updated_by",
    "type",
    "url",
]

# Application field types for validation
APPLICATION_FIELD_TYPES = {
    "name": str,  # Application name
    "description": str,  # Application description
    "status": str,  # Application status
    "version": str,  # Version string (e.g., "1.0.0")
    "platform": str,  # Platform name (e.g., "android", "ios", "web")
    "logo": str,  # Logo URL
    "is_deleted": bool,  # Soft delete flag
    "type": str,  # Application type (e.g., "PWA", "RPM")
    "url": str,  # Application URL
}

# Valid platform values
VALID_PLATFORMS = [
    "android",
    "ios",
    "web",
    "windows",
    "macos",
    "linux",
]

# Valid status values
VALID_STATUS = [
    "active",
    "inactive",
    "pending",
    "archived",
    "deleted",
]

# Valid application type values
VALID_APPLICATION_TYPES = [
    "PWA",
    "RPM",
]
