from aws_cdk import (
    Stack,
    aws_apigateway as apigateway,
    aws_cognito as cognito,
    RemovalPolicy,
    aws_iam as iam,
    Duration,
)
from constructs import Construct
from database.dynamodb.tables.devices import create_devices_table
from database.dynamodb.tables.contents import create_contents_table
from database.dynamodb.tables.schedules import create_schedules_table
from database.dynamodb.tables.playlists import create_playlists_table
from database.dynamodb.tables.playbacks import create_playbacks_table
from database.dynamodb.tables.users import create_users_table
from database.dynamodb.tables.organizations import create_organizations_table
from database.dynamodb.tables.applications import create_applications_table
from helpers.create_lambda import create_lambda_function
from helpers.grant_permission import grant_table_permissions
from helpers.api_policies import create_ip_restriction_policy
from helpers.create_cognito import (
    create_cognito_user_pool,
    create_cognito_user_pool_client,
    create_cognito_identity_pool,
    create_cognito_groups,
)
from helpers.create_layer import create_lambda_layer
from helpers.create_s3 import create_content_bucket
from helpers.grant_permission import grant_s3_permissions


class IkHxrCmsBackendStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        env_name: str = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        IOT_API_URL = "https://hoavw9kvxg.execute-api.us-east-2.amazonaws.com/dev"

        env_name_capitalized = env_name.capitalize() if env_name else "Dev"

        # Create purpose-specific Lambda layers
        auth_dependencies_layer = create_lambda_layer(
            scope=self,
            construct_id="AuthDependenciesLayer",
            layer_name=f"Cms-AuthDependencies-{env_name_capitalized}",
            code_path="src/layers/auth-dependencies",
            description="JWT and cryptography dependencies for authentication functions",
        )

        common_dependencies_layer = create_lambda_layer(
            scope=self,
            construct_id="CommonDependenciesLayer",
            layer_name=f"Cms-CommonDependencies-{env_name_capitalized}",
            code_path="src/layers/common-dependencies",
            description="Common dependencies like requests for API calls",
        )

        # Create Cognito User Pool
        user_pool = create_cognito_user_pool(self, env_name)

        # Create Cognito User Pool Client
        user_pool_client = create_cognito_user_pool_client(self, user_pool, env_name)

        # Create Cognito Identity Pool
        identity_pool = create_cognito_identity_pool(
            self, user_pool, user_pool_client, env_name
        )

        # Create Cognito Groups
        cognito_groups = create_cognito_groups(self, user_pool, env_name)

        # Create DynamoDB tables
        devices_table = create_devices_table(self, env_name)
        contents_table = create_contents_table(self, env_name)
        schedules_table = create_schedules_table(self, env_name)
        playlists_table = create_playlists_table(self, env_name)
        playbacks_table = create_playbacks_table(self, env_name)
        users_table = create_users_table(self, env_name)
        organizations_table = create_organizations_table(self, env_name)
        applications_table = create_applications_table(self, env_name)

        # Create S3 bucket for content storage
        content_bucket = create_content_bucket(self, env_name)

        # Create Lambda Authorizer with auth dependencies
        lambda_authorizer = create_lambda_function(
            scope=self,
            construct_id="LambdaAuthorizerFunction",
            function_name=f"Cms-LambdaAuthorizer-{env_name_capitalized}",
            handler="lambda_authorizer.handler",
            code_path="src/lambda/auth",
            environment={
                "USER_POOL_ID": user_pool.user_pool_id,
                "USER_POOL_CLIENT_ID": user_pool_client.user_pool_client_id,
                "ENV": env_name,
            },
            layers=[auth_dependencies_layer, common_dependencies_layer],
        )

        lambda_authorizer.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "cognito-idp:GetUser",
                    "cognito-idp:AdminGetUser",
                ],
                resources=[user_pool.user_pool_arn],
            )
        )

        # Create Auth Lambda functions with auth dependencies
        login_lambda = create_lambda_function(
            scope=self,
            construct_id="LoginFunction",
            function_name=f"Cms-Login-{env_name_capitalized}",
            handler="login.handler",
            code_path="src/lambda/auth",
            environment={
                "USER_POOL_ID": user_pool.user_pool_id,
                "USER_POOL_CLIENT_ID": user_pool_client.user_pool_client_id,
                "ENV": env_name,
            },
            layers=[auth_dependencies_layer, common_dependencies_layer],
        )

        change_password_lambda = create_lambda_function(
            scope=self,
            construct_id="ChangePasswordFunction",
            function_name=f"Cms-ChangePassword-{env_name_capitalized}",
            handler="change_password.handler",
            code_path="src/lambda/auth",
            environment={
                "USER_POOL_ID": user_pool.user_pool_id,
                "USER_POOL_CLIENT_ID": user_pool_client.user_pool_client_id,
                "USERS_TABLE_NAME": users_table.table_name,
                "ENV": env_name,
            },
            layers=[auth_dependencies_layer, common_dependencies_layer],
        )

        refresh_token_lambda = create_lambda_function(
            scope=self,
            construct_id="RefreshTokenFunction",
            function_name=f"Cms-RefreshToken-{env_name_capitalized}",
            handler="refresh_token.handler",
            code_path="src/lambda/auth",
            environment={
                "USER_POOL_ID": user_pool.user_pool_id,
                "USER_POOL_CLIENT_ID": user_pool_client.user_pool_client_id,
                "ENV": env_name,
            },
            layers=[auth_dependencies_layer, common_dependencies_layer],
        )

        # Grant Cognito permissions to auth Lambda functions
        login_lambda.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "cognito-idp:AdminInitiateAuth",
                    "cognito-idp:AdminRespondToAuthChallenge",
                    "cognito-idp:AdminGetUser",
                ],
                resources=[user_pool.user_pool_arn],
            )
        )

        change_password_lambda.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "cognito-idp:AdminRespondToAuthChallenge",
                    "cognito-idp:AdminGetUser",
                ],
                resources=[user_pool.user_pool_arn],
            )
        )

        refresh_token_lambda.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "cognito-idp:InitiateAuth",
                ],
                resources=[user_pool.user_pool_arn],
            )
        )

        # Create Lambda functions
        create_device_lambda = create_lambda_function(
            scope=self,
            construct_id="CreateDeviceFunction",
            function_name=f"Cms-CreateDevice-{env_name_capitalized}",
            handler="create_device.handler",
            code_path="src/lambda/device",
            environment={
                "DEVICES_TABLE_NAME": devices_table.table_name,
                "ENV": env_name,
            },
        )

        get_device_lambda = create_lambda_function(
            scope=self,
            construct_id="GetDeviceByIdFunction",
            function_name=f"Cms-GetDeviceById-{env_name_capitalized}",
            handler="get_device_by_id.handler",
            code_path="src/lambda/device",
            environment={
                "DEVICES_TABLE_NAME": devices_table.table_name,
                "CONTENTS_TABLE_NAME": contents_table.table_name,
                "PLAYLISTS_TABLE_NAME": playlists_table.table_name,
                "APPLICATIONS_TABLE_NAME": applications_table.table_name,
                "ENV": env_name,
            },
        )

        update_device_lambda = create_lambda_function(
            scope=self,
            construct_id="UpdateDeviceByIdFunction",
            function_name=f"Cms-UpdateDeviceById-{env_name_capitalized}",
            handler="update_device_by_id.handler",
            code_path="src/lambda/device",
            environment={
                "DEVICES_TABLE_NAME": devices_table.table_name,
                "CONTENTS_TABLE_NAME": contents_table.table_name,
                "CONTENT_BUCKET_NAME": content_bucket.bucket_name,
                "IOT_ASSIGN_API_URL": IOT_API_URL + "/assign",
                "ENV": env_name,
            },
            layers=[common_dependencies_layer],
        )

        get_devices_by_org_lambda = create_lambda_function(
            scope=self,
            construct_id="GetDevicesByOrgFunction",
            function_name=f"Cms-GetDevicesByOrg-{env_name_capitalized}",
            handler="get_all_devices_by_org_id.handler",
            code_path="src/lambda/device",
            environment={
                "DEVICES_TABLE_NAME": devices_table.table_name,
                "ENV": env_name,
            },
        )

        update_device_last_seen_lambda = create_lambda_function(
            scope=self,
            construct_id="UpdateDeviceLastSeenFunction",
            function_name=f"Cms-UpdateDeviceLastSeen-{env_name_capitalized}",
            handler="update_device_last_seen.handler",
            code_path="src/lambda/device",
            environment={
                "DEVICES_TABLE_NAME": devices_table.table_name,
                "CONTENTS_TABLE_NAME": contents_table.table_name,
                "PLAYBACKS_TABLE_NAME": playbacks_table.table_name,
                "SCHEDULES_TABLE_NAME": schedules_table.table_name,
                "ENV": env_name,
            },
        )

        # Create Content Lambda functions
        create_content_lambda = create_lambda_function(
            scope=self,
            construct_id="CreateContentFunction",
            function_name=f"Cms-CreateContent-{env_name_capitalized}",
            handler="create_content.handler",
            code_path="src/lambda/content",
            environment={
                "CONTENTS_TABLE_NAME": contents_table.table_name,
                "ENV": env_name,
            },
        )

        get_content_lambda = create_lambda_function(
            scope=self,
            construct_id="GetContentByIdFunction",
            function_name=f"Cms-GetContentById-{env_name_capitalized}",
            handler="get_content_by_id.handler",
            code_path="src/lambda/content",
            environment={
                "CONTENTS_TABLE_NAME": contents_table.table_name,
                "ENV": env_name,
            },
        )

        update_content_lambda = create_lambda_function(
            scope=self,
            construct_id="UpdateContentByIdFunction",
            function_name=f"Cms-UpdateContentById-{env_name_capitalized}",
            handler="update_content_by_id.handler",
            code_path="src/lambda/content",
            environment={
                "CONTENTS_TABLE_NAME": contents_table.table_name,
                "ENV": env_name,
            },
        )

        get_contents_by_org_lambda = create_lambda_function(
            scope=self,
            construct_id="GetContentsByOrgFunction",
            function_name=f"Cms-GetContentsByOrg-{env_name_capitalized}",
            handler="get_all_contents_by_org_id.handler",
            code_path="src/lambda/content",
            environment={
                "CONTENTS_TABLE_NAME": contents_table.table_name,
                "ENV": env_name,
            },
        )

        # Create Upload Content Lambda function
        upload_content_lambda = create_lambda_function(
            scope=self,
            construct_id="UploadContentFunction",
            function_name=f"Cms-UploadContent-{env_name_capitalized}",
            handler="upload_content.handler",
            code_path="src/lambda/content",
            environment={
                "CONTENT_BUCKET_NAME": content_bucket.bucket_name,
                "ENV": env_name,
            },
        )

        # Grant S3 permissions to upload content Lambda
        grant_s3_permissions(upload_content_lambda, content_bucket, "write")

        # Create Get Content Presigned URL Lambda function
        get_content_presigned_url_lambda = create_lambda_function(
            scope=self,
            construct_id="GetContentPresignedUrlFunction",
            function_name=f"Cms-GetContentPresignedUrl-{env_name_capitalized}",
            handler="get_content_presigned_url.handler",
            code_path="src/lambda/content",
            environment={
                "CONTENT_BUCKET_NAME": content_bucket.bucket_name,
                "ENV": env_name,
            },
        )

        # Grant S3 permissions to presigned URL Lambda
        grant_s3_permissions(get_content_presigned_url_lambda, content_bucket, "read")

        # Create Update Content Approval Status Lambda function
        update_content_approval_status_lambda = create_lambda_function(
            scope=self,
            construct_id="UpdateContentApprovalStatusFunction",
            function_name=f"Cms-UpdateContentApprovalStatus-{env_name_capitalized}",
            handler="update_content_status.handler",
            code_path="src/lambda/content",
            environment={
                "CONTENTS_TABLE_NAME": contents_table.table_name,
                "ENV": env_name,
            },
        )

        # Create Schedule Lambda functions
        create_schedule_lambda = create_lambda_function(
            scope=self,
            construct_id="CreateScheduleFunction",
            function_name=f"Cms-CreateSchedule-{env_name_capitalized}",
            handler="create_schedule.handler",
            code_path="src/lambda/schedule",
            environment={
                "SCHEDULES_TABLE_NAME": schedules_table.table_name,
                "PLAYLISTS_TABLE_NAME": playlists_table.table_name,
                "CONTENTS_TABLE_NAME": contents_table.table_name,
                "APPLICATIONS_TABLE_NAME": applications_table.table_name,
                "PLAYBACKS_TABLE_NAME": playbacks_table.table_name,
                "IOT_SCHEDULE_API_URL": IOT_API_URL + "/schedule",
                "CONTENT_BUCKET_NAME": content_bucket.bucket_name,
                "DEVICES_TABLE_NAME": devices_table.table_name,
                "ENV": env_name,
            },
            layers=[common_dependencies_layer],
        )

        get_schedule_lambda = create_lambda_function(
            scope=self,
            construct_id="GetScheduleByIdFunction",
            function_name=f"Cms-GetScheduleById-{env_name_capitalized}",
            handler="get_schedule_by_id.handler",
            code_path="src/lambda/schedule",
            environment={
                "SCHEDULES_TABLE_NAME": schedules_table.table_name,
                "ENV": env_name,
            },
            layers=[common_dependencies_layer],
        )

        update_schedule_lambda = create_lambda_function(
            scope=self,
            construct_id="UpdateScheduleByIdFunction",
            function_name=f"Cms-UpdateScheduleById-{env_name_capitalized}",
            handler="update_schedule_by_id.handler",
            code_path="src/lambda/schedule",
            environment={
                "SCHEDULES_TABLE_NAME": schedules_table.table_name,
                "ENV": env_name,
            },
            layers=[common_dependencies_layer],
        )

        get_schedules_by_org_lambda = create_lambda_function(
            scope=self,
            construct_id="GetSchedulesByOrgFunction",
            function_name=f"Cms-GetSchedulesByOrg-{env_name_capitalized}",
            handler="get_all_schedules_by_org_id.handler",
            code_path="src/lambda/schedule",
            environment={
                "SCHEDULES_TABLE_NAME": schedules_table.table_name,
                "ENV": env_name,
            },
            layers=[common_dependencies_layer],
        )

        # Create Playlist Lambda functions
        create_playlist_lambda = create_lambda_function(
            scope=self,
            construct_id="CreatePlaylistFunction",
            function_name=f"Cms-CreatePlaylist-{env_name_capitalized}",
            handler="create_playlist.handler",
            code_path="src/lambda/playlist",
            environment={
                "PLAYLISTS_TABLE_NAME": playlists_table.table_name,
                "ENV": env_name,
            },
        )

        get_playlist_lambda = create_lambda_function(
            scope=self,
            construct_id="GetPlaylistByIdFunction",
            function_name=f"Cms-GetPlaylistById-{env_name_capitalized}",
            handler="get_playlist_by_id.handler",
            code_path="src/lambda/playlist",
            environment={
                "PLAYLISTS_TABLE_NAME": playlists_table.table_name,
                "ENV": env_name,
            },
        )

        update_playlist_lambda = create_lambda_function(
            scope=self,
            construct_id="UpdatePlaylistByIdFunction",
            function_name=f"Cms-UpdatePlaylistById-{env_name_capitalized}",
            handler="update_playlist_by_id.handler",
            code_path="src/lambda/playlist",
            environment={
                "PLAYLISTS_TABLE_NAME": playlists_table.table_name,
                "ENV": env_name,
            },
        )

        get_playlists_by_org_lambda = create_lambda_function(
            scope=self,
            construct_id="GetPlaylistsByOrgFunction",
            function_name=f"Cms-GetPlaylistsByOrg-{env_name_capitalized}",
            handler="get_all_playlists_by_org_id.handler",
            code_path="src/lambda/playlist",
            environment={
                "PLAYLISTS_TABLE_NAME": playlists_table.table_name,
                "ENV": env_name,
            },
        )

        get_playback_lambda = create_lambda_function(
            scope=self,
            construct_id="GetPlaybackFunction",
            function_name=f"Cms-GetPlayback-{env_name_capitalized}",
            handler="get_playback_by_id.handler",
            code_path="src/lambda/playback",
            environment={
                "PLAYBACKS_TABLE_NAME": playbacks_table.table_name,
                "ENV": env_name,
            },
            layers=[common_dependencies_layer],
        )

        get_playbacks_by_org_lambda = create_lambda_function(
            scope=self,
            construct_id="GetPlaybacksByOrgFunction",
            function_name=f"Cms-GetPlaybacksByOrg-{env_name_capitalized}",
            handler="get_all_playbacks_by_org_id.handler",
            code_path="src/lambda/playback",
            environment={
                "PLAYBACKS_TABLE_NAME": playbacks_table.table_name,
                "ENV": env_name,
            },
            layers=[common_dependencies_layer],
        )

        # Create User Lambda functions
        get_user_lambda = create_lambda_function(
            scope=self,
            construct_id="GetUserByIdFunction",
            function_name=f"Cms-GetUserById-{env_name_capitalized}",
            handler="get_user_by_id.handler",
            code_path="src/lambda/user",
            environment={
                "USERS_TABLE_NAME": users_table.table_name,
                "ENV": env_name,
            },
        )

        update_user_lambda = create_lambda_function(
            scope=self,
            construct_id="UpdateUserByIdFunction",
            function_name=f"Cms-UpdateUserById-{env_name_capitalized}",
            handler="update_user_by_id.handler",
            code_path="src/lambda/user",
            environment={
                "USERS_TABLE_NAME": users_table.table_name,
                "ENV": env_name,
            },
        )

        get_users_by_org_lambda = create_lambda_function(
            scope=self,
            construct_id="GetUsersByOrgFunction",
            function_name=f"Cms-GetUsersByOrg-{env_name_capitalized}",
            handler="get_all_users_by_org_id.handler",
            code_path="src/lambda/user",
            environment={
                "USERS_TABLE_NAME": users_table.table_name,
                "ENV": env_name,
            },
        )

        # Create Organization Lambda functions
        create_organization_lambda = create_lambda_function(
            scope=self,
            construct_id="CreateOrganizationFunction",
            function_name=f"Cms-CreateOrganization-{env_name_capitalized}",
            handler="create_organization.handler",
            code_path="src/lambda/organization",
            environment={
                "ORGANIZATIONS_TABLE_NAME": organizations_table.table_name,
                "ENV": env_name,
            },
        )

        get_organization_lambda = create_lambda_function(
            scope=self,
            construct_id="GetOrganizationByIdFunction",
            function_name=f"Cms-GetOrganizationById-{env_name_capitalized}",
            handler="get_organization_by_id.handler",
            code_path="src/lambda/organization",
            environment={
                "ORGANIZATIONS_TABLE_NAME": organizations_table.table_name,
                "ENV": env_name,
            },
        )

        update_organization_lambda = create_lambda_function(
            scope=self,
            construct_id="UpdateOrganizationByIdFunction",
            function_name=f"Cms-UpdateOrganizationById-{env_name_capitalized}",
            handler="update_organization_by_id.handler",
            code_path="src/lambda/organization",
            environment={
                "ORGANIZATIONS_TABLE_NAME": organizations_table.table_name,
                "ENV": env_name,
            },
        )

        get_all_organizations_lambda = create_lambda_function(
            scope=self,
            construct_id="GetAllOrganizationsFunction",
            function_name=f"Cms-GetAllOrganizations-{env_name_capitalized}",
            handler="get_all_organizations.handler",
            code_path="src/lambda/organization",
            environment={
                "ORGANIZATIONS_TABLE_NAME": organizations_table.table_name,
                "ENV": env_name,
            },
        )

        # Create Application Lambda functions
        create_application_lambda = create_lambda_function(
            scope=self,
            construct_id="CreateApplicationFunction",
            function_name=f"Cms-CreateApplication-{env_name_capitalized}",
            handler="create_application.handler",
            code_path="src/lambda/application",
            environment={
                "APPLICATIONS_TABLE_NAME": applications_table.table_name,
                "ENV": env_name,
            },
        )

        get_application_lambda = create_lambda_function(
            scope=self,
            construct_id="GetApplicationByIdFunction",
            function_name=f"Cms-GetApplicationById-{env_name_capitalized}",
            handler="get_application_by_id.handler",
            code_path="src/lambda/application",
            environment={
                "APPLICATIONS_TABLE_NAME": applications_table.table_name,
                "ENV": env_name,
            },
        )

        update_application_lambda = create_lambda_function(
            scope=self,
            construct_id="UpdateApplicationByIdFunction",
            function_name=f"Cms-UpdateApplicationById-{env_name_capitalized}",
            handler="update_application_by_id.handler",
            code_path="src/lambda/application",
            environment={
                "APPLICATIONS_TABLE_NAME": applications_table.table_name,
                "ENV": env_name,
            },
        )

        get_applications_by_org_lambda = create_lambda_function(
            scope=self,
            construct_id="GetApplicationsByOrgFunction",
            function_name=f"Cms-GetApplicationsByOrg-{env_name_capitalized}",
            handler="get_all_applications_by_org_id.handler",
            code_path="src/lambda/application",
            environment={
                "APPLICATIONS_TABLE_NAME": applications_table.table_name,
                "ENV": env_name,
            },
        )

        # Create new specialized Device Lambda functions
        assign_content_to_device_lambda = create_lambda_function(
            scope=self,
            construct_id="AssignContentToDeviceFunction",
            function_name=f"Cms-AssignContentToDevice-{env_name_capitalized}",
            handler="assign_content_to_device.handler",
            code_path="src/lambda/device",
            environment={
                "DEVICES_TABLE_NAME": devices_table.table_name,
                "CONTENTS_TABLE_NAME": contents_table.table_name,
                "CONTENT_BUCKET_NAME": content_bucket.bucket_name,
                "IOT_ASSIGN_API_URL": IOT_API_URL + "/assign",
                "ENV": env_name,
            },
            layers=[common_dependencies_layer],
        )

        assign_playlist_to_device_lambda = create_lambda_function(
            scope=self,
            construct_id="AssignPlaylistToDeviceFunction",
            function_name=f"Cms-AssignPlaylistToDevice-{env_name_capitalized}",
            handler="assign_playlist_to_device.handler",
            code_path="src/lambda/device",
            environment={
                "DEVICES_TABLE_NAME": devices_table.table_name,
                "PLAYLISTS_TABLE_NAME": playlists_table.table_name,
                "CONTENTS_TABLE_NAME": contents_table.table_name,
                "CONTENT_BUCKET_NAME": content_bucket.bucket_name,
                "IOT_ASSIGN_API_URL": IOT_API_URL + "/assign",
                "ENV": env_name,
            },
            layers=[common_dependencies_layer],
        )

        assign_app_to_device_lambda = create_lambda_function(
            scope=self,
            construct_id="AssignAppToDeviceFunction",
            function_name=f"Cms-AssignAppToDevice-{env_name_capitalized}",
            handler="assign_app_to_device.handler",
            code_path="src/lambda/device",
            environment={
                "DEVICES_TABLE_NAME": devices_table.table_name,
                "APPLICATIONS_TABLE_NAME": applications_table.table_name,
                "ENV": env_name,
            },
            layers=[common_dependencies_layer],
        )

        remove_content_from_device_lambda = create_lambda_function(
            scope=self,
            construct_id="RemoveContentFromDeviceFunction",
            function_name=f"Cms-RemoveContentFromDevice-{env_name_capitalized}",
            handler="remove_content_from_device.handler",
            code_path="src/lambda/device",
            environment={
                "DEVICES_TABLE_NAME": devices_table.table_name,
                "CONTENTS_TABLE_NAME": contents_table.table_name,
                "CONTENT_BUCKET_NAME": content_bucket.bucket_name,
                "IOT_DELETE_CONTENT_API_URL": IOT_API_URL + "/ct-delete",
                "ENV": env_name,
            },
            layers=[common_dependencies_layer],
        )

        remove_playlist_from_device_lambda = create_lambda_function(
            scope=self,
            construct_id="RemovePlaylistFromDeviceFunction",
            function_name=f"Cms-RemovePlaylistFromDevice-{env_name_capitalized}",
            handler="remove_playlist_from_device.handler",
            code_path="src/lambda/device",
            environment={
                "DEVICES_TABLE_NAME": devices_table.table_name,
                "PLAYLISTS_TABLE_NAME": playlists_table.table_name,
                "CONTENTS_TABLE_NAME": contents_table.table_name,
                "CONTENT_BUCKET_NAME": content_bucket.bucket_name,
                "IOT_DELETE_CONTENT_API_URL": IOT_API_URL + "/ct-delete",
                "ENV": env_name,
            },
            layers=[common_dependencies_layer],
        )

        remove_app_from_device_lambda = create_lambda_function(
            scope=self,
            construct_id="RemoveAppFromDeviceFunction",
            function_name=f"Cms-RemoveAppFromDevice-{env_name_capitalized}",
            handler="remove_app_from_device.handler",
            code_path="src/lambda/device",
            environment={
                "DEVICES_TABLE_NAME": devices_table.table_name,
                "APPLICATIONS_TABLE_NAME": applications_table.table_name,
                "ENV": env_name,
            },
            layers=[common_dependencies_layer],
        )

        # Create Content Status Update Lambda function
        update_content_status_lambda = create_lambda_function(
            scope=self,
            construct_id="UpdateContentStatusFunction",
            function_name=f"Cms-UpdateContentStatus-{env_name_capitalized}",
            handler="update_content_status.handler",
            code_path="src/lambda/device",
            environment={
                "DEVICES_TABLE_NAME": devices_table.table_name,
                "CONTENTS_TABLE_NAME": contents_table.table_name,
                "ENV": env_name,
            },
        )

        # Create Device IoT Lambda functions (moved to device/iot directory)
        configure_device_brightness_lambda = create_lambda_function(
            scope=self,
            construct_id="ConfigureDeviceBrightnessFunction",
            function_name=f"Cms-ConfigureDeviceBrightness-{env_name_capitalized}",
            handler="configure_device_brightness.handler",
            code_path="src/lambda/device/iot",
            environment={
                "DEVICES_TABLE_NAME": devices_table.table_name,
                "IOT_API_URL": IOT_API_URL + "/config",
                "ENV": env_name,
            },
            layers=[common_dependencies_layer],
        )

        configure_device_volume_lambda = create_lambda_function(
            scope=self,
            construct_id="ConfigureDeviceVolumeFunction",
            function_name=f"Cms-ConfigureDeviceVolume-{env_name_capitalized}",
            handler="configure_device_volume.handler",
            code_path="src/lambda/device/iot",
            environment={
                "DEVICES_TABLE_NAME": devices_table.table_name,
                "IOT_API_URL": IOT_API_URL + "/config",
                "ENV": env_name,
            },
            layers=[common_dependencies_layer],
        )

        configure_device_wifi_lambda = create_lambda_function(
            scope=self,
            construct_id="ConfigureDeviceWifiFunction",
            function_name=f"Cms-ConfigureDeviceWifi-{env_name_capitalized}",
            handler="configure_device_wifi.handler",
            code_path="src/lambda/device/iot",
            environment={
                "DEVICES_TABLE_NAME": devices_table.table_name,
                "IOT_API_URL": IOT_API_URL + "/config",
                "ENV": env_name,
            },
            layers=[common_dependencies_layer],
        )

        generic_command_lambda = create_lambda_function(
            scope=self,
            construct_id="GenericCommandFunction",
            function_name=f"Cms-GenericCommand-{env_name_capitalized}",
            handler="generic_command.handler",
            code_path="src/lambda/device/iot",
            environment={
                "DEVICES_TABLE_NAME": devices_table.table_name,
                "IOT_COMMAND_API_URL": IOT_API_URL + "/command",
                "ENV": env_name,
            },
            layers=[common_dependencies_layer],
        )

        # Create Base Video Upload Lambda function
        upload_base_video_lambda = create_lambda_function(
            scope=self,
            construct_id="UploadBaseVideoFunction",
            function_name=f"Cms-UploadBaseVideo-{env_name_capitalized}",
            handler="upload_base_video.handler",
            code_path="src/lambda/device",
            environment={
                "DEVICES_TABLE_NAME": devices_table.table_name,
                "CONTENT_BUCKET_NAME": content_bucket.bucket_name,
                "ENV": env_name,
            },
        )

        # Create Update Device Base Content Lambda function
        update_device_base_content_lambda = create_lambda_function(
            scope=self,
            construct_id="UpdateDeviceBaseContentFunction",
            function_name=f"Cms-UpdateDeviceBaseContent-{env_name_capitalized}",
            handler="update_device_base_content.handler",
            code_path="src/lambda/device",
            environment={
                "DEVICES_TABLE_NAME": devices_table.table_name,
                "CONTENT_BUCKET_NAME": content_bucket.bucket_name,
                "IOT_UPDATE_API_URL": IOT_API_URL + "/lp-update",
                "ENV": env_name,
            },
            layers=[common_dependencies_layer],
        )

        # Create Status Update Lambda function
        update_status_lambda = create_lambda_function(
            scope=self,
            construct_id="UpdateStatusFunction",
            function_name=f"Cms-UpdateStatus-{env_name_capitalized}",
            handler="update_status.handler",
            code_path="src/lambda/status",
            environment={
                "DEVICES_TABLE_NAME": devices_table.table_name,
                "CONTENTS_TABLE_NAME": contents_table.table_name,
                "PLAYLISTS_TABLE_NAME": playlists_table.table_name,
                "SCHEDULES_TABLE_NAME": schedules_table.table_name,
                "APPLICATIONS_TABLE_NAME": applications_table.table_name,
                "PLAYBACKS_TABLE_NAME": playbacks_table.table_name,
                "ENV": env_name,
            },
        )

        # Grant table permissions to Lambda functions
        grant_table_permissions(create_device_lambda, devices_table, "write")
        grant_table_permissions(get_device_lambda, devices_table, "read")
        grant_table_permissions(get_device_lambda, contents_table, "read")
        grant_table_permissions(get_device_lambda, playlists_table, "read")
        grant_table_permissions(get_device_lambda, applications_table, "read")
        grant_table_permissions(update_device_lambda, devices_table, "read_write")
        grant_table_permissions(update_device_lambda, contents_table, "read")
        grant_table_permissions(get_devices_by_org_lambda, devices_table, "read")
        grant_table_permissions(update_device_last_seen_lambda, devices_table, "read_write")
        grant_table_permissions(update_device_last_seen_lambda, contents_table, "read")
        grant_table_permissions(update_device_last_seen_lambda, playbacks_table, "read_write")
        grant_table_permissions(update_device_last_seen_lambda, schedules_table, "read")
        grant_table_permissions(upload_base_video_lambda, devices_table, "read")
        
        # Grant S3 permissions to upload base video Lambda
        grant_s3_permissions(upload_base_video_lambda, content_bucket, "write")
        
        grant_table_permissions(update_device_base_content_lambda, devices_table, "read_write")

        grant_table_permissions(create_content_lambda, contents_table, "write")
        grant_table_permissions(get_content_lambda, contents_table, "read")
        grant_table_permissions(update_content_lambda, contents_table, "read_write")
        grant_table_permissions(get_contents_by_org_lambda, contents_table, "read")
        grant_table_permissions(update_content_approval_status_lambda, contents_table, "read_write")

        grant_table_permissions(create_schedule_lambda, schedules_table, "write")
        grant_table_permissions(create_schedule_lambda, playlists_table, "read")
        grant_table_permissions(create_schedule_lambda, contents_table, "read")
        grant_table_permissions(create_schedule_lambda, applications_table, "read")
        grant_table_permissions(create_schedule_lambda, playbacks_table, "write")
        grant_table_permissions(create_schedule_lambda, devices_table, "read_write")
        grant_table_permissions(get_schedule_lambda, schedules_table, "read")
        grant_table_permissions(update_schedule_lambda, schedules_table, "read_write")
        grant_table_permissions(get_schedules_by_org_lambda, schedules_table, "read")

        grant_table_permissions(create_playlist_lambda, playlists_table, "write")
        grant_table_permissions(get_playlist_lambda, playlists_table, "read")
        grant_table_permissions(update_playlist_lambda, playlists_table, "read_write")
        grant_table_permissions(get_playlists_by_org_lambda, playlists_table, "read")

        grant_table_permissions(get_playback_lambda, playbacks_table, "read")
        grant_table_permissions(get_playbacks_by_org_lambda, playbacks_table, "read")

        grant_table_permissions(get_user_lambda, users_table, "read")
        grant_table_permissions(update_user_lambda, users_table, "read_write")
        grant_table_permissions(get_users_by_org_lambda, users_table, "read")

        grant_table_permissions(
            create_organization_lambda, organizations_table, "write"
        )
        grant_table_permissions(get_organization_lambda, organizations_table, "read")
        grant_table_permissions(
            update_organization_lambda, organizations_table, "read_write"
        )
        grant_table_permissions(
            get_all_organizations_lambda, organizations_table, "read"
        )

        grant_table_permissions(create_application_lambda, applications_table, "write")
        grant_table_permissions(get_application_lambda, applications_table, "read")
        grant_table_permissions(update_application_lambda, applications_table, "read_write")
        grant_table_permissions(
            get_applications_by_org_lambda, applications_table, "read"
        )

        # Grant table permissions to new specialized device Lambda functions
        grant_table_permissions(assign_content_to_device_lambda, devices_table, "read_write")
        grant_table_permissions(assign_content_to_device_lambda, contents_table, "read")
        grant_table_permissions(assign_playlist_to_device_lambda, devices_table, "read_write")
        grant_table_permissions(assign_playlist_to_device_lambda, playlists_table, "read")
        grant_table_permissions(assign_playlist_to_device_lambda, contents_table, "read")
        grant_table_permissions(assign_app_to_device_lambda, devices_table, "read_write")
        grant_table_permissions(assign_app_to_device_lambda, applications_table, "read")
        grant_table_permissions(remove_content_from_device_lambda, devices_table, "read_write")
        grant_table_permissions(remove_content_from_device_lambda, contents_table, "read")
        grant_table_permissions(remove_playlist_from_device_lambda, devices_table, "read_write")
        grant_table_permissions(remove_playlist_from_device_lambda, playlists_table, "read")
        grant_table_permissions(remove_app_from_device_lambda, devices_table, "read_write")
        grant_table_permissions(remove_app_from_device_lambda, applications_table, "read")

        # Grant table permissions to Content Status Update Lambda function
        grant_table_permissions(update_content_status_lambda, devices_table, "read_write")
        grant_table_permissions(update_content_status_lambda, contents_table, "read")

        # Grant table permissions to Device IoT Lambda functions
        grant_table_permissions(configure_device_brightness_lambda, devices_table, "read")
        grant_table_permissions(configure_device_volume_lambda, devices_table, "read")
        grant_table_permissions(configure_device_wifi_lambda, devices_table, "read")
        grant_table_permissions(generic_command_lambda, devices_table, "read")

        # Grant table permissions to Status Update Lambda function
        grant_table_permissions(update_status_lambda, devices_table, "read_write")
        grant_table_permissions(update_status_lambda, contents_table, "read_write")
        grant_table_permissions(update_status_lambda, playlists_table, "read_write")
        grant_table_permissions(update_status_lambda, schedules_table, "read_write")
        grant_table_permissions(update_status_lambda, applications_table, "read_write")
        grant_table_permissions(update_status_lambda, playbacks_table, "read_write")

        # Create Cognito Lambda functions
        create_cognito_user_lambda = create_lambda_function(
            scope=self,
            construct_id="CreateCognitoUserFunction",
            function_name=f"Cms-CreateCognitoUser-{env_name_capitalized}",
            handler="create_cognito_user.handler",
            code_path="src/lambda/cognito",
            environment={
                "USER_POOL_ID": user_pool.user_pool_id,
                "USERS_TABLE_NAME": users_table.table_name,
                "ORGANIZATIONS_TABLE_NAME": organizations_table.table_name,
                "ENV": env_name,
            },
        )

        # Grant Cognito permissions to Cognito Lambda functions
        create_cognito_user_lambda.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "cognito-idp:AdminCreateUser",
                    "cognito-idp:AdminAddUserToGroup",
                    "cognito-idp:AdminGetUser",
                ],
                resources=[user_pool.user_pool_arn],
            )
        )

        grant_table_permissions(create_cognito_user_lambda, users_table, "read_write")
        grant_table_permissions(create_cognito_user_lambda, organizations_table, "read_write")
        grant_table_permissions(change_password_lambda, users_table, "read_write")


        # Create API Gateway with Lambda Authorizer
        api = apigateway.RestApi(
            self,
            "CmsApi",
            rest_api_name=f"cms-api-{env_name}",
            description="CMS Backend API",
            # Remove policy for dev environment to avoid signing issues
            deploy_options=apigateway.StageOptions(
                stage_name=env_name or "dev",
                throttling_rate_limit=1000,
                throttling_burst_limit=500,
            ),
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=["*"],
                allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH", "HEAD"],
                allow_headers=[
                    "Content-Type",
                    "Authorization",
                    "X-Amz-Date",
                    "X-Api-Key",
                    "X-Amz-Security-Token",
                    "X-Amz-User-Agent",
                    "X-Requested-With",
                    "Origin",
                    "Accept",
                    "Cache-Control",
                    "Pragma",
                    "If-Modified-Since",
                    "X-Forwarded-For",
                    "X-Forwarded-Proto",
                    "X-Forwarded-Port",
                ],
                expose_headers=["Date", "X-Amzn-ErrorType", "X-Amzn-RequestId", "X-Amz-Request-Id"],
                max_age=Duration.seconds(86400),
                allow_credentials=False,
            ),
        )

        # Create Lambda Authorizer
        authorizer = apigateway.TokenAuthorizer(
            self,
            "CmsTokenAuthorizer",
            handler=lambda_authorizer,
            identity_source="method.request.header.Authorization",
        )

        # ------------------------------------- DEVICE API -------------------------------------
        # Base device API resources
        device_resource = api.root.add_resource("device")
        device_id_resource = device_resource.add_resource("{id}")
        organization_resource = device_resource.add_resource("organization")
        org_id_resource = organization_resource.add_resource("{orgId}")
        device_last_seen_resource = device_resource.add_resource("status")

        # Lambda integrations for basic device operations
        create_device_integration = apigateway.LambdaIntegration(create_device_lambda)
        get_device_integration = apigateway.LambdaIntegration(get_device_lambda)
        update_device_integration = apigateway.LambdaIntegration(update_device_lambda)
        get_devices_by_org_integration = apigateway.LambdaIntegration(
            get_devices_by_org_lambda
        )
        update_device_last_seen_integration = apigateway.LambdaIntegration(
            update_device_last_seen_lambda
        )

        # Basic device API methods
        device_resource.add_method(
            "POST", create_device_integration, authorizer=authorizer
        )
        device_id_resource.add_method(
            "GET", get_device_integration, authorizer=authorizer
        )
        device_id_resource.add_method(
            "PUT", update_device_integration, authorizer=authorizer
        )
        org_id_resource.add_method(
            "GET", get_devices_by_org_integration, authorizer=authorizer
        )
        
        # Device last seen update endpoint (no auth required for device self-reporting)
        device_last_seen_resource.add_method(
            "POST", update_device_last_seen_integration
        )

        # Device Assignment API Resources and Methods
        # Content assignment
        assign_content_resource = device_id_resource.add_resource("assign-content")
        assign_content_integration = apigateway.LambdaIntegration(assign_content_to_device_lambda)
        assign_content_resource.add_method("POST", assign_content_integration, authorizer=authorizer)

        # Playlist assignment
        assign_playlist_resource = device_id_resource.add_resource("assign-playlist")
        assign_playlist_integration = apigateway.LambdaIntegration(assign_playlist_to_device_lambda)
        assign_playlist_resource.add_method("POST", assign_playlist_integration, authorizer=authorizer)

        # Application assignment
        assign_app_resource = device_id_resource.add_resource("assign-app")
        assign_app_integration = apigateway.LambdaIntegration(assign_app_to_device_lambda)
        assign_app_resource.add_method("POST", assign_app_integration, authorizer=authorizer)

        # Device Removal API Resources and Methods
        # Content removal
        remove_content_resource = device_id_resource.add_resource("remove-content")
        remove_content_integration = apigateway.LambdaIntegration(remove_content_from_device_lambda)
        remove_content_resource.add_method("POST", remove_content_integration, authorizer=authorizer)

        # Playlist removal
        remove_playlist_resource = device_id_resource.add_resource("remove-playlist")
        remove_playlist_integration = apigateway.LambdaIntegration(remove_playlist_from_device_lambda)
        remove_playlist_resource.add_method("POST", remove_playlist_integration, authorizer=authorizer)

        # Application removal
        remove_app_resource = device_id_resource.add_resource("remove-app")
        remove_app_integration = apigateway.LambdaIntegration(remove_app_from_device_lambda)
        remove_app_resource.add_method("POST", remove_app_integration, authorizer=authorizer)

        # Content Status Update API Resource and Method
        content_status_resource = device_id_resource.add_resource("content-status")
        content_status_integration = apigateway.LambdaIntegration(update_content_status_lambda)
        content_status_resource.add_method("POST", content_status_integration, authorizer=authorizer)

        # Device IoT Configuration API Resources and Methods
        config_resource = device_id_resource.add_resource("config")

        # Brightness configuration
        brightness_config_resource = config_resource.add_resource("brightness")
        brightness_config_integration = apigateway.LambdaIntegration(configure_device_brightness_lambda)
        brightness_config_resource.add_method("POST", brightness_config_integration, authorizer=authorizer)

        # Volume configuration
        volume_config_resource = config_resource.add_resource("volume")
        volume_config_integration = apigateway.LambdaIntegration(configure_device_volume_lambda)
        volume_config_resource.add_method("POST", volume_config_integration, authorizer=authorizer)

        # WiFi configuration
        wifi_config_resource = config_resource.add_resource("wifi")
        wifi_config_integration = apigateway.LambdaIntegration(configure_device_wifi_lambda)
        wifi_config_resource.add_method("POST", wifi_config_integration, authorizer=authorizer)

        # Generic command
        command_resource = device_id_resource.add_resource("command")
        command_integration = apigateway.LambdaIntegration(generic_command_lambda)
        command_resource.add_method("POST", command_integration, authorizer=authorizer)

        # Base Video Upload API Resource and Method
        upload_base_video_resource = device_id_resource.add_resource("upload-base-video")
        upload_base_video_integration = apigateway.LambdaIntegration(upload_base_video_lambda)
        upload_base_video_resource.add_method("POST", upload_base_video_integration, authorizer=authorizer)

        # Update Device Base Content API Resource and Method
        update_base_content_resource = device_id_resource.add_resource("base-content")
        update_base_content_integration = apigateway.LambdaIntegration(update_device_base_content_lambda)
        update_base_content_resource.add_method("POST", update_base_content_integration, authorizer=authorizer)
        # ------------------------------------- END OF DEVICE API -------------------------------------

        # ------------------------------------- CONTENT API -------------------------------------
        # API resources
        content_resource = api.root.add_resource("content")
        content_id_resource = content_resource.add_resource("{id}")
        content_organization_resource = content_resource.add_resource("organization")
        content_org_id_resource = content_organization_resource.add_resource("{orgId}")

        # Lambda integrations
        create_content_integration = apigateway.LambdaIntegration(create_content_lambda)
        get_content_integration = apigateway.LambdaIntegration(get_content_lambda)
        update_content_integration = apigateway.LambdaIntegration(update_content_lambda)
        get_contents_by_org_integration = apigateway.LambdaIntegration(
            get_contents_by_org_lambda
        )
        upload_content_integration = apigateway.LambdaIntegration(upload_content_lambda)
        get_content_presigned_url_integration = apigateway.LambdaIntegration(
            get_content_presigned_url_lambda
        )

        # Content API methods
        content_resource.add_method(
            "POST", create_content_integration, authorizer=authorizer
        )
        content_id_resource.add_method(
            "GET", get_content_integration, authorizer=authorizer
        )
        content_id_resource.add_method(
            "PUT", update_content_integration, authorizer=authorizer
        )
        content_org_id_resource.add_method(
            "GET", get_contents_by_org_integration, authorizer=authorizer
        )

        # Upload content endpoint
        content_upload_resource = content_resource.add_resource("upload")
        content_upload_resource.add_method(
            "POST", upload_content_integration, authorizer=authorizer
        )

        # Content URL endpoint
        content_url_resource = content_resource.add_resource("url")
        content_url_resource.add_method(
            "POST", get_content_presigned_url_integration, authorizer=authorizer
        )

        # Content Status Update endpoint
        content_status_integration = apigateway.LambdaIntegration(update_content_approval_status_lambda)
        content_status_resource = content_id_resource.add_resource("status")
        content_status_resource.add_method(
            "PATCH", content_status_integration, authorizer=authorizer
        )
        # ------------------------------------- END OF CONTENT API -------------------------------------

        # ------------------------------------- SCHEDULE API -------------------------------------
        # API resources
        schedule_resource = api.root.add_resource("schedule")
        schedule_id_resource = schedule_resource.add_resource("{id}")
        schedule_organization_resource = schedule_resource.add_resource("organization")
        schedule_org_id_resource = schedule_organization_resource.add_resource(
            "{orgId}"
        )

        # Create Schedule Lambda integrations
        create_schedule_integration = apigateway.LambdaIntegration(
            create_schedule_lambda
        )
        get_schedule_integration = apigateway.LambdaIntegration(get_schedule_lambda)
        update_schedule_integration = apigateway.LambdaIntegration(
            update_schedule_lambda
        )
        get_schedules_by_org_integration = apigateway.LambdaIntegration(
            get_schedules_by_org_lambda
        )

        # Add Schedule API methods
        schedule_resource.add_method(
            "POST", create_schedule_integration, authorizer=authorizer
        )
        schedule_id_resource.add_method(
            "GET", get_schedule_integration, authorizer=authorizer
        )
        schedule_id_resource.add_method(
            "PUT", update_schedule_integration, authorizer=authorizer
        )
        schedule_org_id_resource.add_method(
            "GET", get_schedules_by_org_integration, authorizer=authorizer
        )
        # ------------------------------------- END OF SCHEDULE API -------------------------------------

        # ------------------------------------- PLAYLIST API -------------------------------------
        # API resources
        playlist_resource = api.root.add_resource("playlist")
        playlist_id_resource = playlist_resource.add_resource("{id}")
        playlist_organization_resource = playlist_resource.add_resource("organization")
        playlist_org_id_resource = playlist_organization_resource.add_resource(
            "{orgId}"
        )

        # Lambda integrations
        create_playlist_integration = apigateway.LambdaIntegration(
            create_playlist_lambda
        )
        get_playlist_integration = apigateway.LambdaIntegration(get_playlist_lambda)
        update_playlist_integration = apigateway.LambdaIntegration(
            update_playlist_lambda
        )
        get_playlists_by_org_integration = apigateway.LambdaIntegration(
            get_playlists_by_org_lambda
        )

        # Add playlist API methods
        playlist_resource.add_method(
            "POST", create_playlist_integration, authorizer=authorizer
        )
        playlist_id_resource.add_method(
            "GET", get_playlist_integration, authorizer=authorizer
        )
        playlist_id_resource.add_method(
            "PUT", update_playlist_integration, authorizer=authorizer
        )
        playlist_org_id_resource.add_method(
            "GET", get_playlists_by_org_integration, authorizer=authorizer
        )
        # ------------------------------------- END OF PLAYLIST API -------------------------------------

        # ------------------------------------- PLAYBACK API -------------------------------------
        # API resources
        playback_resource = api.root.add_resource("playback")
        playback_id_resource = playback_resource.add_resource("{id}")
        playback_organization_resource = playback_resource.add_resource("organization")
        playback_org_id_resource = playback_organization_resource.add_resource(
            "{orgId}"
        )

        # Lambda integrations
        get_playback_integration = apigateway.LambdaIntegration(get_playback_lambda)
        get_playbacks_by_org_integration = apigateway.LambdaIntegration(
            get_playbacks_by_org_lambda
        )

        # Add playback API methods
        # Get APIs with authorizer (for authenticated users)
        playback_id_resource.add_method("GET", get_playback_integration, authorizer=authorizer)
        playback_org_id_resource.add_method("GET", get_playbacks_by_org_integration, authorizer=authorizer)
        # ------------------------------------- END OF PLAYBACK API -------------------------------------

        # ------------------------------------- USER API -------------------------------------
        # API resources
        user_resource = api.root.add_resource("user")
        user_id_resource = user_resource.add_resource("{id}")
        user_organization_resource = user_resource.add_resource("organization")
        user_org_id_resource = user_organization_resource.add_resource("{orgId}")

        # Lambda integrations
        get_user_integration = apigateway.LambdaIntegration(get_user_lambda)
        update_user_integration = apigateway.LambdaIntegration(update_user_lambda)
        get_users_by_org_integration = apigateway.LambdaIntegration(
            get_users_by_org_lambda
        )

        # Add user API methods
        user_id_resource.add_method("GET", get_user_integration, authorizer=authorizer)
        user_id_resource.add_method(
            "PUT", update_user_integration, authorizer=authorizer
        )
        user_org_id_resource.add_method(
            "GET", get_users_by_org_integration, authorizer=authorizer
        )
        # ------------------------------------- END OF USER API -------------------------------------

        # ------------------------------------- ORGANIZATION API -------------------------------------
        # API resources
        organization_resource = api.root.add_resource("organization")
        organization_id_resource = organization_resource.add_resource("{id}")

        # Lambda integrations
        create_organization_integration = apigateway.LambdaIntegration(
            create_organization_lambda
        )
        get_organization_integration = apigateway.LambdaIntegration(
            get_organization_lambda
        )
        update_organization_integration = apigateway.LambdaIntegration(
            update_organization_lambda
        )
        get_all_organizations_integration = apigateway.LambdaIntegration(
            get_all_organizations_lambda
        )

        # Add organization API methods
        organization_resource.add_method(
            "POST", create_organization_integration, authorizer=authorizer
        )
        organization_resource.add_method(
            "GET", get_all_organizations_integration, authorizer=authorizer
        )
        organization_id_resource.add_method(
            "GET", get_organization_integration, authorizer=authorizer
        )
        organization_id_resource.add_method(
            "PUT", update_organization_integration, authorizer=authorizer
        )
        # ------------------------------------- END OF ORGANIZATION API -------------------------------------

        # ------------------------------------- APPLICATION API -------------------------------------
        # API resources
        application_resource = api.root.add_resource("application")
        application_id_resource = application_resource.add_resource("{id}")
        application_organization_resource = application_resource.add_resource(
            "organization"
        )
        application_org_id_resource = application_organization_resource.add_resource(
            "{orgId}"
        )

        # Lambda integrations
        create_application_integration = apigateway.LambdaIntegration(
            create_application_lambda
        )
        get_application_integration = apigateway.LambdaIntegration(
            get_application_lambda
        )
        update_application_integration = apigateway.LambdaIntegration(
            update_application_lambda
        )
        get_applications_by_org_integration = apigateway.LambdaIntegration(
            get_applications_by_org_lambda
        )

        # Add application API methods
        application_resource.add_method(
            "POST", create_application_integration, authorizer=authorizer
        )
        application_id_resource.add_method(
            "GET", get_application_integration, authorizer=authorizer
        )
        application_id_resource.add_method(
            "PUT", update_application_integration, authorizer=authorizer
        )
        application_org_id_resource.add_method(
            "GET", get_applications_by_org_integration, authorizer=authorizer
        )
        # ------------------------------------- END OF APPLICATION API -------------------------------------

        # ------------------------------------- STATUS API -------------------------------------
        # API resources
        status_resource = api.root.add_resource("status")

        # Lambda integrations
        update_status_integration = apigateway.LambdaIntegration(update_status_lambda)

        # Add status API methods
        # TODO: Add a separate authorizer for this endpoint
        status_resource.add_method(
            "POST", update_status_integration
        )
        # ------------------------------------- END OF STATUS API -------------------------------------

        # Add auth endpoints (no authentication required)
        auth_resource = api.root.add_resource("auth")
        login_resource = auth_resource.add_resource("login")
        change_password_resource = auth_resource.add_resource("change-password")
        refresh_token_resource = auth_resource.add_resource("refresh")

        login_integration = apigateway.LambdaIntegration(login_lambda)
        change_password_integration = apigateway.LambdaIntegration(
            change_password_lambda
        )
        refresh_token_integration = apigateway.LambdaIntegration(refresh_token_lambda)

        login_resource.add_method("POST", login_integration)
        change_password_resource.add_method("POST", change_password_integration)
        refresh_token_resource.add_method("POST", refresh_token_integration)

        # Add new Cognito endpoints
        cognito_resource = api.root.add_resource("cognito")
        create_user_resource = cognito_resource.add_resource("create")

        create_user_integration = apigateway.LambdaIntegration(
            create_cognito_user_lambda
        )

        create_user_resource.add_method(
            "POST", create_user_integration, authorizer=authorizer
        )


