# Required fields for schedule creation
REQUIRED_SCHEDULE_FIELDS = [
    {
        "name": "Start At",
        "column_name": "start_at",
    },
    {
        "name": "Organization ID",
        "column_name": "organization_id",
    },
]

# Optional fields for schedule creation and updates
OPTIONAL_SCHEDULE_FIELDS = [
    "end_at",
    "loop",
    "is_active",
    "is_deleted",
    "assigned_to",
    "contents",
    "playlists",
    "created_by",
    "updated_by",
]

# Schedule field types for validation
SCHEDULE_FIELD_TYPES = {
    "start_at": str,  # ISO 8601 datetime string
    "end_at": str,  # ISO 8601 datetime string
    "loop": bool,  # Whether to loop the schedule
    "is_active": bool,  # Whether the schedule is active
    "is_deleted": bool,  # Soft delete flag
}
