from aws_cdk import (
    Stack,
    aws_apigateway as apigateway,
)
from constructs import Construct
from database.dynamodb.tables.devices import create_devices_table
from database.dynamodb.tables.contents import create_contents_table
from database.dynamodb.tables.schedules import create_schedules_table
from database.dynamodb.tables.playlists import create_playlists_table
from database.dynamodb.tables.users import create_users_table
from database.dynamodb.tables.organizations import create_organizations_table
from helpers.create_lambda import create_lambda_function
from helpers.grant_permission import grant_table_permissions
from helpers.api_policies import create_ip_restriction_policy


class IkHxrCmsBackendStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        env_name: str = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        env_name_capitalized = env_name.capitalize() if env_name else "Dev"

        # Create DynamoDB tables
        devices_table = create_devices_table(self, env_name)
        contents_table = create_contents_table(self, env_name)
        schedules_table = create_schedules_table(self, env_name)
        playlists_table = create_playlists_table(self, env_name)
        users_table = create_users_table(self, env_name)
        organizations_table = create_organizations_table(self, env_name)

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
                "ENV": env_name,
            },
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

        # Create Schedule Lambda functions
        create_schedule_lambda = create_lambda_function(
            scope=self,
            construct_id="CreateScheduleFunction",
            function_name=f"Cms-CreateSchedule-{env_name_capitalized}",
            handler="create_schedule.handler",
            code_path="src/lambda/schedule",
            environment={
                "SCHEDULES_TABLE_NAME": schedules_table.table_name,
                "ENV": env_name,
            },
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
        )

        # Create playlist Lambda functions
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

        # Create User Lambda functions
        create_user_lambda = create_lambda_function(
            scope=self,
            construct_id="CreateUserFunction",
            function_name=f"Cms-CreateUser-{env_name_capitalized}",
            handler="create_user.handler",
            code_path="src/lambda/user",
            environment={
                "USERS_TABLE_NAME": users_table.table_name,
                "ENV": env_name,
            },
        )

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

        # Grant table permissions
        grant_table_permissions(create_device_lambda, devices_table, "write")
        grant_table_permissions(get_device_lambda, devices_table, "read")
        grant_table_permissions(update_device_lambda, devices_table, "read_write")
        grant_table_permissions(get_devices_by_org_lambda, devices_table, "read")

        # Grant content table permissions
        grant_table_permissions(create_content_lambda, contents_table, "write")
        grant_table_permissions(get_content_lambda, contents_table, "read")
        grant_table_permissions(update_content_lambda, contents_table, "read_write")
        grant_table_permissions(get_contents_by_org_lambda, contents_table, "read")

        # Grant schedule table permissions
        grant_table_permissions(create_schedule_lambda, schedules_table, "write")
        grant_table_permissions(get_schedule_lambda, schedules_table, "read")
        grant_table_permissions(update_schedule_lambda, schedules_table, "read_write")
        grant_table_permissions(get_schedules_by_org_lambda, schedules_table, "read")

        # Grant playlist table permissions
        grant_table_permissions(create_playlist_lambda, playlists_table, "write")
        grant_table_permissions(get_playlist_lambda, playlists_table, "read")
        grant_table_permissions(update_playlist_lambda, playlists_table, "read_write")
        grant_table_permissions(get_playlists_by_org_lambda, playlists_table, "read")

        # Grant user table permissions
        grant_table_permissions(create_user_lambda, users_table, "read_write")
        grant_table_permissions(get_user_lambda, users_table, "read")
        grant_table_permissions(update_user_lambda, users_table, "read_write")
        grant_table_permissions(get_users_by_org_lambda, users_table, "read")

        # Grant organization table permissions
        grant_table_permissions(
            create_organization_lambda, organizations_table, "read_write"
        )
        grant_table_permissions(get_organization_lambda, organizations_table, "read")
        grant_table_permissions(
            update_organization_lambda, organizations_table, "read_write"
        )
        grant_table_permissions(
            get_all_organizations_lambda, organizations_table, "read"
        )

        # Create API Gateway with IP restriction policy
        api = apigateway.RestApi(
            self,
            "CmsApi",
            rest_api_name=f"cms-api-{env_name}",
            description="CMS Backend API",
            policy=create_ip_restriction_policy(env_name),
            deploy_options=apigateway.StageOptions(
                stage_name=env_name or "dev",
                throttling_rate_limit=1000,
                throttling_burst_limit=500,
            ),
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS,
                allow_headers=apigateway.Cors.DEFAULT_HEADERS,
            ),
        )

        # ------------------------------------- DEVICE API -------------------------------------
        # API resources
        device_resource = api.root.add_resource("device")
        device_id_resource = device_resource.add_resource("{id}")
        organization_resource = device_resource.add_resource("organization")
        org_id_resource = organization_resource.add_resource("{orgId}")

        # Lambda integrations
        create_device_integration = apigateway.LambdaIntegration(create_device_lambda)
        get_device_integration = apigateway.LambdaIntegration(get_device_lambda)
        update_device_integration = apigateway.LambdaIntegration(update_device_lambda)
        get_devices_by_org_integration = apigateway.LambdaIntegration(
            get_devices_by_org_lambda
        )

        # API methods
        device_resource.add_method("POST", create_device_integration)
        device_id_resource.add_method("GET", get_device_integration)
        device_id_resource.add_method("PUT", update_device_integration)
        org_id_resource.add_method("GET", get_devices_by_org_integration)
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

        # Content API methods
        content_resource.add_method("POST", create_content_integration)
        content_id_resource.add_method("GET", get_content_integration)
        content_id_resource.add_method("PUT", update_content_integration)
        content_org_id_resource.add_method("GET", get_contents_by_org_integration)
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
        schedule_resource.add_method("POST", create_schedule_integration)
        schedule_id_resource.add_method("GET", get_schedule_integration)
        schedule_id_resource.add_method("PUT", update_schedule_integration)
        schedule_org_id_resource.add_method("GET", get_schedules_by_org_integration)
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
        playlist_resource.add_method("POST", create_playlist_integration)
        playlist_id_resource.add_method("GET", get_playlist_integration)
        playlist_id_resource.add_method("PUT", update_playlist_integration)
        playlist_org_id_resource.add_method("GET", get_playlists_by_org_integration)
        # ------------------------------------- END OF PLAYLIST API -------------------------------------

        # ------------------------------------- USER API -------------------------------------
        # API resources
        user_resource = api.root.add_resource("user")
        user_id_resource = user_resource.add_resource("{id}")
        user_organization_resource = user_resource.add_resource("organization")
        user_org_id_resource = user_organization_resource.add_resource("{orgId}")

        # Lambda integrations
        create_user_integration = apigateway.LambdaIntegration(create_user_lambda)
        get_user_integration = apigateway.LambdaIntegration(get_user_lambda)
        update_user_integration = apigateway.LambdaIntegration(update_user_lambda)
        get_users_by_org_integration = apigateway.LambdaIntegration(
            get_users_by_org_lambda
        )

        # Add user API methods
        user_resource.add_method("POST", create_user_integration)
        user_id_resource.add_method("GET", get_user_integration)
        user_id_resource.add_method("PUT", update_user_integration)
        user_org_id_resource.add_method("GET", get_users_by_org_integration)
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
        organization_resource.add_method("POST", create_organization_integration)
        organization_resource.add_method("GET", get_all_organizations_integration)
        organization_id_resource.add_method("GET", get_organization_integration)
        organization_id_resource.add_method("PUT", update_organization_integration)
        # ------------------------------------- END OF ORGANIZATION API -------------------------------------
