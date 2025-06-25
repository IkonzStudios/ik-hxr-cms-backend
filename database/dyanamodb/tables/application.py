from aws_cdk import aws_dynamodb as dynamodb, RemovalPolicy
from constructs import Construct

def create_application_table(scope: Construct, env_name: str = None) -> dynamodb.Table:
    """Create and return a DynamoDB table for applications."""
    return dynamodb.Table(
        scope,
        id="ApplicationsTable",
        table_name=f"cms-applications-{env_name}" if env_name else "cms-applications",
        partition_key=dynamodb.Attribute(name="id", type=dynamodb.AttributeType.STRING),
        billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
        removal_policy=RemovalPolicy.RETAIN,
        # point_in_time_recovery_specification=dynamodb.CfnTable.PointInTimeRecoverySpecificationProperty(
        #     point_in_time_recovery_enabled=True
        # ),
        # point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
        #     enabled=True  
        # ),
        # point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
        #     point_in_time_recovery=True
        # ),

        # point_in_time_recovery=True
        encryption=dynamodb.TableEncryption.AWS_MANAGED,
    )

