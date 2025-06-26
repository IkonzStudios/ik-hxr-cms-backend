from aws_cdk import aws_lambda as lambda_, Duration
from constructs import Construct
from pathlib import Path

def create_lambda(
    scope: Construct,
    construct_id: str,
    function_name: str,
    handler: str,
    code_path: str,
    environment: dict = None,
    runtime: lambda_.Runtime = lambda_.Runtime.PYTHON_3_11,
    memory_size: int = 256,
    timeout_sec: int = 10,
) -> lambda_.Function:
    """
    Creates an AWS Lambda function.

    Args:
        scope (Construct): CDK construct scope.
        construct_id (str): CDK logical ID.
        function_name (str): Name of the function in AWS Console.
        handler (str): Python file and handler function (e.g. "main.handler").
        code_path (str): Path to the folder containing the Lambda code.
        environment (dict, optional): Environment variables.
        runtime (aws_lambda.Runtime, optional): Runtime version.
        memory_size (int, optional): Memory allocated to the function.
        timeout_sec (int, optional): Timeout in seconds.

    Returns:
        aws_lambda.Function: The created Lambda function.
    """

    return lambda_.Function(
        scope,
        construct_id,
        function_name=function_name,
        runtime=runtime,
        handler=handler,
        code=lambda_.Code.from_asset(str(Path(code_path).resolve())),
        memory_size=memory_size,
        timeout=Duration.seconds(timeout_sec),  # ✅ Correct usage
        environment=environment or {},
    )
