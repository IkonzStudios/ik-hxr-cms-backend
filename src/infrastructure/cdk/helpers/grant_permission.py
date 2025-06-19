from aws_cdk import aws_lambda as lambda_


def grant_table_permissions(
    lambda_function: lambda_.Function,
    table,
    permissions: str
):
    """
    Grant DynamoDB table permissions to a Lambda function.
    
    Args:
        lambda_function: The Lambda function to grant permissions to
        table: The DynamoDB table
        permissions: Type of permissions ('read', 'write', 'read_write')
    """
    if permissions == 'read':
        table.grant_read_data(lambda_function)
    elif permissions == 'write':
        table.grant_write_data(lambda_function)
    elif permissions == 'read_write':
        table.grant_read_write_data(lambda_function)
    else:
        raise ValueError(f"Invalid permissions: {permissions}. Use 'read', 'write', or 'read_write'")


def grant_multiple_table_permissions(
    lambda_function: lambda_.Function,
    tables_and_permissions: list
):
    """
    Grant multiple DynamoDB table permissions to a Lambda function.
    
    Args:
        lambda_function: The Lambda function to grant permissions to
        tables_and_permissions: List of tuples (table, permissions)
                               e.g., [(devices_table, 'read'), (users_table, 'write')]
    """
    for table, permissions in tables_and_permissions:
        grant_table_permissions(lambda_function, table, permissions)


def grant_s3_permissions(
    lambda_function: lambda_.Function,
    bucket,
    permissions: str
):
    """
    Grant S3 bucket permissions to a Lambda function.
    
    Args:
        lambda_function: The Lambda function to grant permissions to
        bucket: The S3 bucket
        permissions: Type of permissions ('read', 'write', 'read_write', 'delete')
    """
    if permissions == 'read':
        bucket.grant_read(lambda_function)
    elif permissions == 'write':
        bucket.grant_write(lambda_function)
    elif permissions == 'read_write':
        bucket.grant_read_write(lambda_function)
    elif permissions == 'delete':
        bucket.grant_delete(lambda_function)
    else:
        raise ValueError(f"Invalid permissions: {permissions}. Use 'read', 'write', 'read_write', or 'delete'")


def grant_sns_permissions(
    lambda_function: lambda_.Function,
    topic,
    permissions: str = 'publish'
):
    """
    Grant SNS topic permissions to a Lambda function.
    
    Args:
        lambda_function: The Lambda function to grant permissions to
        topic: The SNS topic
        permissions: Type of permissions ('publish', 'subscribe')
    """
    if permissions == 'publish':
        topic.grant_publish(lambda_function)
    elif permissions == 'subscribe':
        topic.grant_subscribe(lambda_function)
    else:
        raise ValueError(f"Invalid permissions: {permissions}. Use 'publish' or 'subscribe'")


def grant_sqs_permissions(
    lambda_function: lambda_.Function,
    queue,
    permissions: str
):
    """
    Grant SQS queue permissions to a Lambda function.
    
    Args:
        lambda_function: The Lambda function to grant permissions to
        queue: The SQS queue
        permissions: Type of permissions ('send', 'receive', 'consume')
    """
    if permissions == 'send':
        queue.grant_send_messages(lambda_function)
    elif permissions == 'receive':
        queue.grant_consume_messages(lambda_function)
    elif permissions == 'consume':
        queue.grant_consume_messages(lambda_function)
    else:
        raise ValueError(f"Invalid permissions: {permissions}. Use 'send', 'receive', or 'consume'")
