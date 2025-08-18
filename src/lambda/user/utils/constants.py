# Required fields for user creation
REQUIRED_USER_FIELDS = [
    {
        "name": "First Name",
        "column_name": "first_name",
    },
    {
        "name": "Last Name",
        "column_name": "last_name",
    },
    {
        "name": "Email",
        "column_name": "email",
    },
    {
        "name": "Role",
        "column_name": "role",
    },
    {
        "name": "Password",
        "column_name": "password",
    },
    {
        "name": "Organization ID",
        "column_name": "organization_id",
    },
]

# Valid user roles
VALID_USER_ROLES = [
    "superadmin",
    "admin",
    "user",
    "viewer",
]
