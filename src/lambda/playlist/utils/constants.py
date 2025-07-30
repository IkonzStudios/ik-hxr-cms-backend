# Required fields for playlist creation
REQUIRED_PLAYLIST_FIELDS = [
    {
        "name": "Name",
        "column_name": "name",
    },
    {
        "name": "Organization ID",
        "column_name": "organization_id",
    },
]

# Optional fields for playlist creation and updates
OPTIONAL_PLAYLIST_FIELDS = [
    "description",
    "contents",
    "is_deleted",
    "created_by",
    "updated_by",
]

# Playlist field types for validation
PLAYLIST_FIELD_TYPES = {
    "name": str,  # Playlist name
    "description": str,  # Playlist description
    "is_deleted": bool,  # Soft delete flag
}
