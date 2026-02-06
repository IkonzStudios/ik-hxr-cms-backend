from aws_cdk import aws_dynamodb as dynamodb, RemovalPolicy
from constructs import Construct


def create_playbacks_table(scope: Construct, env_name: str = None) -> dynamodb.Table:
    """Create and return a DynamoDB table for playbacks."""
    return dynamodb.Table(
        scope,
        id="PlaybacksTable",
        table_name=f"cms-playbacks-{env_name}" if env_name else "cms-playbacks",
        partition_key=dynamodb.Attribute(name="id", type=dynamodb.AttributeType.STRING),
        billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
        removal_policy=RemovalPolicy.RETAIN,
        point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
            point_in_time_recovery_enabled=True
        ),
        encryption=dynamodb.TableEncryption.AWS_MANAGED,
    )
