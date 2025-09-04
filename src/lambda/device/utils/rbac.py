import json
from typing import Dict, Any, Optional


# RBAC Permission Matrix for Device resources
PERMISSIONS = {
    "superadmin": {
        "device": ["create", "edit", "delete", "view", "upload"]
    },
    "admin": {  # ORG ADMIN - can manage within their organization
        "device": ["create", "edit", "delete", "view", "upload"]
    },
    "content_admin": {
        # No device permissions
    },
    "analytics_user": {
        # No device permissions
    },
    "standard_user": {
        "device": ["view"]
    },
    "viewer": {
        "device": ["view"]
    }
}


def get_cors_headers() -> Dict[str, str]:
    """
    Get standard CORS headers for all responses.

    Returns:
        Dictionary with CORS headers
    """
    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token,X-Requested-With,Origin,Accept,Cache-Control,Pragma,If-Modified-Since,X-Forwarded-For,X-Forwarded-Proto,X-Forwarded-Port",
        "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS,PATCH,HEAD",
        "Access-Control-Max-Age": "86400",
    }


def extract_user_info_from_event(event: Dict[str, Any]) -> Dict[str, str]:
    """
    Extract user information from the API Gateway event context.
    
    Args:
        event: The API Gateway event containing request context
        
    Returns:
        Dictionary containing user_id, role, organization_id, and email
    """
    request_context = event.get("requestContext", {})
    authorizer = request_context.get("authorizer", {})
    
    # Handle both direct authorizer context and stringified context
    if isinstance(authorizer, str):
        try:
            authorizer = json.loads(authorizer)
        except (json.JSONDecodeError, TypeError):
            authorizer = {}
    
    return {
        "user_id": authorizer.get("user_id", ""),
        "role": authorizer.get("role", "").lower(),
        "organization_id": authorizer.get("organization_id", ""),
        "email": authorizer.get("email", "")
    }


def check_permission(user_role: str, resource: str, action: str) -> Optional[Dict[str, Any]]:
    """
    Check if a user role has permission to perform an action on a resource.
    
    Args:
        user_role: The user's role (e.g., 'superadmin', 'admin', etc.)
        resource: The resource being accessed (e.g., 'content', 'playlist', etc.)
        action: The action being performed (e.g., 'create', 'view', 'edit', etc.)
        
    Returns:
        None if permission is granted, error response dict if permission is denied
    """
    # Normalize inputs
    user_role = user_role.lower().strip()
    resource = resource.lower().strip()
    action = action.lower().strip()
    
    # Check if role exists in permissions
    if user_role not in PERMISSIONS:
        return create_forbidden_response("You don't have necessary permission to access this resource")
    
    # Check if resource exists for this role
    role_permissions = PERMISSIONS[user_role]
    if resource not in role_permissions:
        return create_forbidden_response("You don't have necessary permission to access this resource")
    
    # Check if action is allowed for this resource
    allowed_actions = role_permissions[resource]
    if action not in allowed_actions:
        return create_forbidden_response("You don't have necessary permission to access this resource")
    
    return None


def check_organization_access(user_org_id: str, resource_org_id: str, user_role: str) -> Optional[Dict[str, Any]]:
    """
    Check if a user has access to a resource based on organization ownership.
    SUPERADMIN can access all organizations, others can only access their own.
    
    Args:
        user_org_id: The user's organization ID
        resource_org_id: The organization ID of the resource being accessed
        user_role: The user's role
        
    Returns:
        None if access is granted, error response dict if access is denied
    """
    user_role = user_role.lower().strip()
    
    # SUPERADMIN can access all organizations
    if user_role == "superadmin":
        return None
    
    # Other roles can only access resources in their own organization
    if user_org_id != resource_org_id:
        return create_forbidden_response("You don't have necessary permission to access this resource")
    
    return None


def create_forbidden_response(message: str = "You don't have necessary permission to access this resource") -> Dict[str, Any]:
    """
    Create a 403 Forbidden response.
    
    Args:
        message: The error message to include in the response
        
    Returns:
        403 error response dictionary
    """
    return {
        "statusCode": 403,
        "headers": get_cors_headers(),
        "body": json.dumps({"error": message})
    }


def validate_rbac_for_handler(event: Dict[str, Any], resource: str, action: str) -> tuple[Optional[Dict[str, Any]], Dict[str, str]]:
    """
    Complete RBAC validation for a Lambda handler.
    
    Args:
        event: The API Gateway event
        resource: The resource being accessed
        action: The action being performed
        
    Returns:
        Tuple of (error_response, user_info)
        If error_response is None, access is granted and user_info contains user details
        If error_response is not None, access is denied and should be returned immediately
    """
    # Extract user information
    user_info = extract_user_info_from_event(event)
    
    # Check if we have required user information
    if not user_info["user_id"] or not user_info["role"]:
        return create_forbidden_response("You don't have necessary permission to access this resource"), user_info
    
    # Check basic permission
    permission_error = check_permission(user_info["role"], resource, action)
    if permission_error:
        return permission_error, user_info
    
    return None, user_info


def validate_rbac_with_org_check(event: Dict[str, Any], resource: str, action: str, resource_org_id: str) -> tuple[Optional[Dict[str, Any]], Dict[str, str]]:
    """
    Complete RBAC validation including organization access check.
    
    Args:
        event: The API Gateway event
        resource: The resource being accessed
        action: The action being performed
        resource_org_id: The organization ID of the resource being accessed
        
    Returns:
        Tuple of (error_response, user_info)
        If error_response is None, access is granted and user_info contains user details
        If error_response is not None, access is denied and should be returned immediately
    """
    # First do basic RBAC validation
    rbac_error, user_info = validate_rbac_for_handler(event, resource, action)
    if rbac_error:
        return rbac_error, user_info
    
    # Then check organization access
    org_error = check_organization_access(user_info["organization_id"], resource_org_id, user_info["role"])
    if org_error:
        return org_error, user_info
    
    return None, user_info


# Convenience functions for common resource/action combinations
def check_create_permission(event: Dict[str, Any], resource: str) -> tuple[Optional[Dict[str, Any]], Dict[str, str]]:
    """Check create permission for a resource."""
    return validate_rbac_for_handler(event, resource, "create")


def check_view_permission(event: Dict[str, Any], resource: str) -> tuple[Optional[Dict[str, Any]], Dict[str, str]]:
    """Check view permission for a resource."""
    return validate_rbac_for_handler(event, resource, "view")


def check_edit_permission(event: Dict[str, Any], resource: str) -> tuple[Optional[Dict[str, Any]], Dict[str, str]]:
    """Check edit permission for a resource."""
    return validate_rbac_for_handler(event, resource, "edit")


def check_delete_permission(event: Dict[str, Any], resource: str) -> tuple[Optional[Dict[str, Any]], Dict[str, str]]:
    """Check delete permission for a resource."""
    return validate_rbac_for_handler(event, resource, "delete")


def check_upload_permission(event: Dict[str, Any], resource: str) -> tuple[Optional[Dict[str, Any]], Dict[str, str]]:
    """Check upload permission for a resource."""
    return validate_rbac_for_handler(event, resource, "upload")


# Organization-aware convenience functions
def check_create_permission_with_org(event: Dict[str, Any], resource: str, org_id: str) -> tuple[Optional[Dict[str, Any]], Dict[str, str]]:
    """Check create permission with organization validation."""
    return validate_rbac_with_org_check(event, resource, "create", org_id)


def check_view_permission_with_org(event: Dict[str, Any], resource: str, org_id: str) -> tuple[Optional[Dict[str, Any]], Dict[str, str]]:
    """Check view permission with organization validation."""
    return validate_rbac_with_org_check(event, resource, "view", org_id)


def check_edit_permission_with_org(event: Dict[str, Any], resource: str, org_id: str) -> tuple[Optional[Dict[str, Any]], Dict[str, str]]:
    """Check edit permission with organization validation."""
    return validate_rbac_with_org_check(event, resource, "edit", org_id)


def check_delete_permission_with_org(event: Dict[str, Any], resource: str, org_id: str) -> tuple[Optional[Dict[str, Any]], Dict[str, str]]:
    """Check delete permission with organization validation."""
    return validate_rbac_with_org_check(event, resource, "delete", org_id)


def check_upload_permission_with_org(event: Dict[str, Any], resource: str, org_id: str) -> tuple[Optional[Dict[str, Any]], Dict[str, str]]:
    """Check upload permission with organization validation."""
    return validate_rbac_with_org_check(event, resource, "upload", org_id)