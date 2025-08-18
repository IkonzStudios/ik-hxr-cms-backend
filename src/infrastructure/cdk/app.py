#!/usr/bin/env python3
import sys
from pathlib import Path
from aws_cdk import App, Environment

# Add the project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# fmt: off
from infrastructure.cdk.stacks.ik_hxr_cms_backend_stack import IkHxrCmsBackendStack  # noqa: E402
# fmt: on

app = App()

env_name = app.node.try_get_context("env") or "dev"

environments = {
    "dev": {"stack_name": "IkHxrCmsBackendStack-Dev", "region": "us-east-2"},
    "stage": {"stack_name": "IkHxrCmsBackendStack-Stage", "region": "us-east-2"},
    "prod": {"stack_name": "IkHxrCmsBackendStack-Prod", "region": "us-east-2"},
}

env_config = environments[env_name]


IkHxrCmsBackendStack(
    app,
    env_config["stack_name"],
    env=Environment(
        account=app.node.try_get_context("account"), region=env_config["region"]
    ),
    env_name=env_name,
)

app.synth()
