# Required fields for playback creation
REQUIRED_PLAYBACK_FIELDS = [
    {
        "name": "Schedule ID",
        "column_name": "schedule_id",
    },
    {
        "name": "Job ID",
        "column_name": "job_id",
    },
    {
        "name": "Content ID",
        "column_name": "content_id",
    },
    {
        "name": "Duration",
        "column_name": "duration",
    },
    {
        "name": "Start At",
        "column_name": "start_at",
    },
    {
        "name": "End At",
        "column_name": "end_at",
    },
    {
        "name": "Organization ID",
        "column_name": "organization_id",
    },
]

# Optional fields for playback creation and updates
OPTIONAL_PLAYBACK_FIELDS = [
    "status",
    "times_played",
    "created_by",
    "updated_by",
]

# Playback field types for validation
PLAYBACK_FIELD_TYPES = {
    "schedule_id": str,  # Schedule ID reference
    "job_id": str,  # Job ID
    "content_id": str,  # Content ID reference
    "duration": int,  # Duration in seconds
    "start_at": str,  # ISO 8601 datetime string
    "end_at": str,  # ISO 8601 datetime string
    "status": str,  # Status: created, playing, completed, failed
    "times_played": int,  # Number of times played
    "is_deleted": bool,  # Soft delete flag
}

# Valid status values
VALID_STATUS_VALUES = ["created", "playing", "completed", "failed"]
