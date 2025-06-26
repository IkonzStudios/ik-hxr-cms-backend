from aws_cdk import Stack, aws_apigateway as apigateway
from constructs import Construct

from database.dyanamodb.tables.application import create_application_table
from infrastructure.cdk.helpers.create_lambda import create_lambda
from infrastructure.cdk.helpers.grant_permissions import grant_permissions


class ApplicationStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, env_name: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        env_name_capitalized = env_name.upper() if env_name else "Dev"

        #Creating DynamoDB Table
        application_table = create_application_table(self, env_name)

        # Create Lambda Functions
        
        create_app_lambda = create_lambda(
            scope=self,
            construct_id="CreateApplicationFunction",
            function_name=f"Cms-CreateApplication-{env_name_capitalized}",
            handler="create_application.handler",
            code_path="lambda/application",
            environment={
                "APPLICATION_TABLE_NAME": application_table.table_name,
                "ENV": env_name,
            },
        )
        get_all_apps_lambda = create_lambda(
            scope=self,
            construct_id="GetAllApplicationsFunction",
            function_name=f"Cms-GetAllApplications-{env_name_capitalized}",
            handler="get_all_applications.handler",
            code_path="lambda/application",
            environment={
                "APPLICATION_TABLE_NAME": application_table.table_name,
                "ENV": env_name,
            },
        )



        get_app_by_id_lambda = create_lambda(
            scope=self,
            construct_id="GetApplicationByIdFunction",
            function_name=f"Cms-GetApplicationById-{env_name_capitalized}",
            handler="get_application_by_id.handler",
            code_path="lambda/application",
            environment={
                "APPLICATION_TABLE_NAME": application_table.table_name,
                "ENV": env_name,
            },
        )


        # Grant Table Permissions (Correct order)
        grant_permissions(
            lambda_function=create_app_lambda,
            resource=application_table,
            service="dynamodb",
            actions=["put_item"]
        )

        grant_permissions(
            lambda_function=get_all_apps_lambda,
            resource=application_table,
            service="dynamodb",
            actions=["scan"]
        )

        grant_permissions(
            lambda_function=get_app_by_id_lambda,
            resource=application_table,
            service="dynamodb",
            actions=["get_item"]
        )


        
        # Create API Gateway
        # api = apigateway.RestApi(self, "ApplicationServiceAPI", rest_api_name=f"application-service-api-{env_name}")
        api = apigateway.RestApi(
            self,
            "ApplicationServiceApi",
            rest_api_name=f"applicationservice-api-{env_name}",
            description="Application Service Backend API",
            deploy_options=apigateway.StageOptions(
                stage_name=env_name or "dev",
                throttling_rate_limit=1000,
                throttling_burst_limit=500,
            ),
            #TODO: Restrict CORS origins in production
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,  # TODO: Change to allowed frontend domain in prod
                allow_methods=apigateway.Cors.ALL_METHODS,
                allow_headers=apigateway.Cors.DEFAULT_HEADERS,
            ),
        )

       
        # Create API Resources
        applications_resource = api.root.add_resource("applications")
        single_app_resource = applications_resource.add_resource("{id}")

        
        # Create Lambda Integrations
        create_app_integration = apigateway.LambdaIntegration(create_app_lambda)
        get_all_apps_integration = apigateway.LambdaIntegration(get_all_apps_lambda)
        get_app_by_id_integration = apigateway.LambdaIntegration(get_app_by_id_lambda)

        
        # Add API Methods
        applications_resource.add_method("POST", create_app_integration)
        applications_resource.add_method("GET", get_all_apps_integration)
        single_app_resource.add_method("GET", get_app_by_id_integration)
