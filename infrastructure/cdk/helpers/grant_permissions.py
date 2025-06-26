from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sqs as sqs
from typing import List, Union

# Centralized fine-grained action map
PERMISSION_ACTIONS = {
    "dynamodb": {
        "get_item": "dynamodb:GetItem",
        "put_item": "dynamodb:PutItem",
        "update_item": "dynamodb:UpdateItem",
        "delete_item": "dynamodb:DeleteItem",
        "query": "dynamodb:Query",
        "scan": "dynamodb:Scan",
        "batch_get_item": "dynamodb:BatchGetItem",
        "batch_write_item": "dynamodb:BatchWriteItem",
    },
    "s3": {
        "get_object": "s3:GetObject",
        "put_object": "s3:PutObject",
        "delete_object": "s3:DeleteObject",
        "list_bucket": "s3:ListBucket",
    },
    "sns": {
        "publish": "sns:Publish",
        "subscribe": "sns:Subscribe",
    },
    "sqs": {
        "send_message": "sqs:SendMessage",
        "receive_message": "sqs:ReceiveMessage",
        "delete_message": "sqs:DeleteMessage",
    },
}


def grant_permissions(
    lambda_function: lambda_.Function,
    resource: Union[dynamodb.Table, s3.Bucket, sns.Topic, sqs.Queue],
    service: str,
    actions: List[str],
    include_indexes: bool = False,
):
    """
    Grant fine-grained IAM permissions to a Lambda function.

    Args:
        lambda_function: Target Lambda function
        resource: AWS resource (Table, Bucket, Topic, Queue)
        service: AWS service ('dynamodb', 's3', 'sns', 'sqs')
        actions: Fine-grained action keys (e.g. ['get_item', 'put_item'])
        include_indexes: (DynamoDB only) Include GSIs/LSIs in resource ARNs
    """
    if service not in PERMISSION_ACTIONS:
        raise ValueError(f"Unsupported service: {service}")

    action_map = PERMISSION_ACTIONS[service]

    invalid = [a for a in actions if a not in action_map]
    if invalid:
        raise ValueError(f"Invalid actions for {service}: {invalid}")

    iam_actions = [action_map[a] for a in actions]

    resource_arns = []

    if service == "dynamodb":
        resource_arns = [resource.table_arn]
        if include_indexes:
            resource_arns.append(f"{resource.table_arn}/index/*")

    elif service == "s3":
        # Bucket ARN for listing; object ARN for actual object ops
        bucket_arn = resource.bucket_arn
        object_arn = f"{bucket_arn}/*"
        for action in iam_actions:
            if "List" in action:
                resource_arns.append(bucket_arn)
            else:
                resource_arns.append(object_arn)

    elif service in {"sns", "sqs"}:
        resource_arns = [resource.topic_arn if service == "sns" else resource.queue_arn]

    lambda_function.add_to_role_policy(
        iam.PolicyStatement(
            actions=iam_actions,
            resources=resource_arns,
        )
    )


def grant_multiple_permissions(
    lambda_function: lambda_.Function,
    permissions: List[dict]
):
    """
    Grant multiple permissions in batch.

    Example:
        grant_multiple_permissions(my_lambda, [
            {"resource": my_table, "service": "dynamodb", "actions": ["get_item"]},
            {"resource": my_bucket, "service": "s3", "actions": ["put_object", "get_object"]}
        ])
    """
    for perm in permissions:
        grant_permissions(
            lambda_function=lambda_function,
            resource=perm["resource"],
            service=perm["service"],
            actions=perm["actions"],
            include_indexes=perm.get("include_indexes", False)
        )
