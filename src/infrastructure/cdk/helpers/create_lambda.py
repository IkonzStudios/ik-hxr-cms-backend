from aws_cdk import (
    aws_lambda as lambda_,
    Duration,
)
from typing import Dict, List, Optional


def create_lambda_function(
    scope,
    construct_id: str,
    function_name: str,
    handler: str,
    code_path: str,
    environment: Dict[str, str] = None,
    timeout_seconds: int = 29,
    runtime: lambda_.Runtime = lambda_.Runtime.PYTHON_3_9,
    memory_size: int = 128,
    layers: Optional[List[lambda_.ILayerVersion]] = None,
) -> lambda_.Function:
    """
    Create a Lambda function with customizable configurations.

    Args:
        scope: The CDK scope/stack
        construct_id: Unique identifier for this Lambda construct (e.g., "GetNoteByIdFunction")
        function_name: Function name (e.g., "GetNoteById-{env_name}")
        handler: The handler method (e.g., "get_note_by_id.handler")
        code_path: Path to the Lambda code (e.g., "src/lambda/notes")
        environment: Environment variables for the Lambda
        timeout_seconds: Timeout in seconds (default: 29)
        runtime: Lambda runtime (default: Python 3.9)
        memory_size: Memory allocation in MB (default: 128)
        layers: List of Lambda layers to attach (default: None)

    Returns:
        lambda_.Function: The created Lambda function
    """
    return lambda_.Function(
        scope,
        construct_id,
        runtime=runtime,
        handler=handler,
        code=lambda_.Code.from_asset(code_path),
        function_name=function_name,
        timeout=Duration.seconds(timeout_seconds),
        environment=environment or {},
        memory_size=memory_size,
        layers=layers or [],
    )
