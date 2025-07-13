# Required fields for content creation
REQUIRED_CONTENT_FIELDS = [
    {
        "name": "Title",
        "column_name": "title",
    },
    {
        "name": "Organization ID",
        "column_name": "organization_id",
    },
    {
        "name": "URL",
        "column_name": "url",
    },
]

# Optional fields for content creation and updates
OPTIONAL_CONTENT_FIELDS = [
    "thumbnail",
    "description",
    "size",
    "duration",
    "type",
    "file_url",
    "is_active",
    "is_deleted",
    "assigned_to",
    "playlists",
    "created_by",
    "updated_by",
]

# Content field types for validation
CONTENT_FIELD_TYPES = {
    "size": int,  # File size in bytes
    "duration": float,  # Duration in seconds
    "type": str,  # File type/category (video, image, document, etc.)
    "file_url": str,  # S3 file URL without prefix
}

# Valid content types
VALID_CONTENT_TYPES = [
    "video/mp4",
]
