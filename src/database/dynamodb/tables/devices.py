from aws_cdk import aws_dynamodb as dynamodb, RemovalPolicy
from constructs import Construct

def create_devices_table(scope: Construct, env_name: str = None) -> dynamodb.Table:
    """Create and return a DynamoDB table for devices."""
    return dynamodb.Table(
        scope,
        id="DevicesTable",
        table_name=f"cms-devices-{env_name}" if env_name else "cms-devices",
        partition_key=dynamodb.Attribute(
            name="id",
            type=dynamodb.AttributeType.STRING
        ),
        billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
        removal_policy=RemovalPolicy.RETAIN,
        point_in_time_recovery=True,
        encryption=dynamodb.TableEncryption.AWS_MANAGED,
    )
