from aws_cdk import (
    aws_cognito as cognito,
    Duration,
    RemovalPolicy,
)

from constructs import Construct


def create_cognito_user_pool(
    scope: Construct,
    env_name: str = None,
) -> cognito.UserPool:
    """Create and return a Cognito User Pool with custom configurations."""

    user_pool = cognito.UserPool(
        scope,
        "CmsUserPool",
        user_pool_name=f"cms-user-pool-{env_name}" if env_name else "cms-user-pool",
        self_sign_up_enabled=False,  # Only admins can create users
        sign_in_aliases=cognito.SignInAliases(email=True),
        standard_attributes=cognito.StandardAttributes(
            email=cognito.StandardAttribute(required=True, mutable=True),
            given_name=cognito.StandardAttribute(required=True, mutable=True),
            family_name=cognito.StandardAttribute(required=True, mutable=True),
        ),
        custom_attributes={
            "organization_id": cognito.StringAttribute(mutable=True),
            "role": cognito.StringAttribute(mutable=True),
            "created_by": cognito.StringAttribute(mutable=True),
            "updated_by": cognito.StringAttribute(mutable=True),
        },
        password_policy=cognito.PasswordPolicy(
            min_length=8,
            require_lowercase=True,
            require_uppercase=True,
            require_digits=True,
            require_symbols=True,
        ),
        account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
        removal_policy=RemovalPolicy.RETAIN,
        user_invitation=cognito.UserInvitationConfig(
            email_subject="Welcome to CMS Platform",
            email_body="Hello {username}, your temporary password is {####}",
            sms_message="Your username is {username} and temporary password is {####}",
        ),
        sign_in_case_sensitive=False,
    )

    return user_pool


def create_cognito_user_pool_client(
    scope: Construct,
    user_pool: cognito.UserPool,
    env_name: str = None,
) -> cognito.UserPoolClient:
    """Create and return a Cognito User Pool Client."""

    user_pool_client = cognito.UserPoolClient(
        scope,
        "CmsUserPoolClient",
        user_pool=user_pool,
        user_pool_client_name=f"cms-client-{env_name}" if env_name else "cms-client",
        generate_secret=False,  # For public clients (web/mobile apps)
        auth_flows=cognito.AuthFlow(
            admin_user_password=True,
            user_password=True,
            custom=True,
        ),
        o_auth=cognito.OAuthSettings(
            flows=cognito.OAuthFlows(
                authorization_code_grant=True,
                implicit_code_grant=True,
            ),
            scopes=[
                cognito.OAuthScope.EMAIL,
                cognito.OAuthScope.OPENID,
                cognito.OAuthScope.PROFILE,
            ],
            callback_urls=[
                "http://localhost:3000/callback"
            ],  # Update with your frontend URL
            logout_urls=[
                "http://localhost:3000/logout"
            ],  # Update with your frontend URL
        ),
        prevent_user_existence_errors=True,
        refresh_token_validity=Duration.days(30),
        access_token_validity=Duration.hours(1),
        id_token_validity=Duration.hours(1),
    )

    return user_pool_client


def create_cognito_identity_pool(
    scope: Construct,
    user_pool: cognito.UserPool,
    user_pool_client: cognito.UserPoolClient,
    env_name: str = None,
) -> cognito.CfnIdentityPool:
    """Create and return a Cognito Identity Pool."""

    identity_pool = cognito.CfnIdentityPool(
        scope,
        "CmsIdentityPool",
        identity_pool_name=f"cms-identity-pool-{env_name}"
        if env_name
        else "cms-identity-pool",
        allow_unauthenticated_identities=False,
        cognito_identity_providers=[
            cognito.CfnIdentityPool.CognitoIdentityProviderProperty(
                client_id=user_pool_client.user_pool_client_id,
                provider_name=user_pool.user_pool_provider_name,
            )
        ],
    )

    return identity_pool


def create_cognito_groups(
    scope: Construct,
    user_pool: cognito.UserPool,
    env_name: str = None,
) -> dict:
    """Create Cognito groups for role-based access control."""

    groups = {}

    # Superadmin group
    superadmin_group = cognito.CfnUserPoolGroup(
        scope,
        "SuperadminGroup",
        user_pool_id=user_pool.user_pool_id,
        group_name="superadmin",
        description="Super administrator with full system access",
        precedence=1,
    )
    groups["superadmin"] = superadmin_group

    # Admin group
    admin_group = cognito.CfnUserPoolGroup(
        scope,
        "AdminGroup",
        user_pool_id=user_pool.user_pool_id,
        group_name="admin",
        description="Organization administrator",
        precedence=2,
    )
    groups["admin"] = admin_group

    # User group
    user_group = cognito.CfnUserPoolGroup(
        scope,
        "UserGroup",
        user_pool_id=user_pool.user_pool_id,
        group_name="user",
        description="Regular user",
        precedence=3,
    )
    groups["user"] = user_group

    # Viewer group
    viewer_group = cognito.CfnUserPoolGroup(
        scope,
        "ViewerGroup",
        user_pool_id=user_pool.user_pool_id,
        group_name="viewer",
        description="Read-only user",
        precedence=4,
    )
    groups["viewer"] = viewer_group

    return groups
