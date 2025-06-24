from aws_cdk import (
    # Duration,
    Stack,
    # aws_sqs as sqs,
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

        # The code that defines your stack goes here

        # example resource
        # queue = sqs.Queue(
        #     self, "IkHxrCmsBackendQueue",
        #     visibility_timeout=Duration.seconds(300),
        # )
