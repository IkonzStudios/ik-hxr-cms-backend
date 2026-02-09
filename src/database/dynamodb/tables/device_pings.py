from aws_cdk import aws_dynamodb as dynamodb, RemovalPolicy
from constructs import Construct


def create_device_pings_table(scope: Construct, env_name: str = None) -> dynamodb.Table:
    """Create and return a DynamoDB table for device online status (pings per device per day)."""
    return dynamodb.Table(
        scope,
        id="DevicePingsTable",
        table_name=f"cms-device-pings-{env_name}" if env_name else "cms-device-pings",
        partition_key=dynamodb.Attribute(name="device_id", type=dynamodb.AttributeType.STRING),
        sort_key=dynamodb.Attribute(name="date", type=dynamodb.AttributeType.STRING),
        billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
        removal_policy=RemovalPolicy.RETAIN,
        point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
            point_in_time_recovery_enabled=True
        ),
        encryption=dynamodb.TableEncryption.AWS_MANAGED,
    )
