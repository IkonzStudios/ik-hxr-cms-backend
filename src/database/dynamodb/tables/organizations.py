from aws_cdk import aws_dynamodb as dynamodb, RemovalPolicy
from constructs import Construct


def create_organizations_table(
    scope: Construct, env_name: str = None
) -> dynamodb.Table:
    """Create and return a DynamoDB table for organizations."""
    return dynamodb.Table(
        scope,
        id="OrganizationsTable",
        table_name=f"cms-organizations-{env_name}" if env_name else "cms-organizations",
        partition_key=dynamodb.Attribute(name="id", type=dynamodb.AttributeType.STRING),
        billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
        removal_policy=RemovalPolicy.RETAIN,
        point_in_time_recovery=True,
        encryption=dynamodb.TableEncryption.AWS_MANAGED,
    )
