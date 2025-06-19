from aws_cdk import (
    # Duration,
    Stack,
    # aws_sqs as sqs,
    aws_dynamodb as dynamodb,
    RemovalPolicy,
)
from constructs import Construct


class IkHxrCmsBackendStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        env_name: str = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Store the environment name as an instance variable
        self.env_name = env_name
