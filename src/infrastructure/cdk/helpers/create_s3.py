from aws_cdk import (
    aws_s3 as s3,
    RemovalPolicy,
    Duration,
)
from constructs import Construct


def create_content_bucket(
    scope: Construct,
    env_name: str = None,
) -> s3.Bucket:
    """Create and return an S3 bucket for content storage."""

    # Create bucket with auto-generated name to avoid conflicts
    bucket = s3.Bucket(
        scope,
        "ContentStorageBucket",
        # Remove bucket_name to let CDK generate a unique name
        versioned=True,
        encryption=s3.BucketEncryption.S3_MANAGED,
        block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
        removal_policy=RemovalPolicy.RETAIN,
        transfer_acceleration=True,
        # Configure CORS for direct uploads from web browsers
        cors=[
            s3.CorsRule(
                allowed_origins=[
                    "*"
                ],  # In production, replace with your frontend domain
                allowed_methods=[
                    s3.HttpMethods.GET,
                    s3.HttpMethods.POST,
                    s3.HttpMethods.PUT,
                    s3.HttpMethods.DELETE,
                    s3.HttpMethods.HEAD,
                ],
                allowed_headers=["*"],
                exposed_headers=[
                    "x-amz-server-side-encryption",
                    "x-amz-request-id",
                    "x-amz-id-2",
                    "ETag",
                ],
                max_age=3000,
            )
        ],
        # No lifecycle rules - files are persistent
    )

    return bucket
