from aws_cdk import (
    aws_lambda as lambda_,
)
from constructs import Construct


def create_lambda_layer(
    scope: Construct,
    construct_id: str,
    layer_name: str,
    code_path: str,
    description: str = None,
    compatible_runtimes: list = None,
) -> lambda_.LayerVersion:
    """
    Create a Lambda Layer for dependencies.

    Args:
        scope: The CDK scope/stack
        construct_id: Unique identifier for this layer construct
        layer_name: Layer name
        code_path: Path to the layer code (should contain the zip file)
        description: Layer description
        compatible_runtimes: List of compatible runtimes

    Returns:
        lambda_.LayerVersion: The created Lambda Layer
    """

    if compatible_runtimes is None:
        compatible_runtimes = [lambda_.Runtime.PYTHON_3_9]

    return lambda_.LayerVersion(
        scope,
        construct_id,
        layer_version_name=layer_name,
        code=lambda_.Code.from_asset(code_path),
        compatible_runtimes=compatible_runtimes,
        description=description or f"Lambda layer for {layer_name}",
    )
