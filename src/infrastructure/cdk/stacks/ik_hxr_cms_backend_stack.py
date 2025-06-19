from aws_cdk import (
    Stack,
    aws_apigateway as apigateway,
)
from constructs import Construct
from database.dynamodb.tables.devices import create_devices_table
from helpers.create_lambda import create_lambda_function
from helpers.grant_permission import grant_table_permissions


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

        # Grant table permissions
        grant_table_permissions(create_device_lambda, devices_table, "write")
        grant_table_permissions(get_device_lambda, devices_table, "read")
        grant_table_permissions(update_device_lambda, devices_table, "read_write")
        grant_table_permissions(get_devices_by_org_lambda, devices_table, "read")

        # Create API Gateway
        api = apigateway.RestApi(
            self,
            "CmsApi",
            rest_api_name=f"cms-api-{env_name}",
            description="CMS Backend API",
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

        # Create API resources
        device_resource = api.root.add_resource("device")
        device_id_resource = device_resource.add_resource("{id}")
        organization_resource = device_resource.add_resource("organization")
        org_id_resource = organization_resource.add_resource("{orgId}")

        # Create Lambda integrations
        create_device_integration = apigateway.LambdaIntegration(create_device_lambda)
        get_device_integration = apigateway.LambdaIntegration(get_device_lambda)
        update_device_integration = apigateway.LambdaIntegration(update_device_lambda)
        get_devices_by_org_integration = apigateway.LambdaIntegration(
            get_devices_by_org_lambda
        )

        # Add API methods
        device_resource.add_method("POST", create_device_integration)
        device_id_resource.add_method("GET", get_device_integration)
        device_id_resource.add_method("PUT", update_device_integration)
        org_id_resource.add_method("GET", get_devices_by_org_integration)
