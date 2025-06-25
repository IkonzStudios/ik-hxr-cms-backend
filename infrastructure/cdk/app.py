#!/usr/bin/env python3
import sys
from pathlib import Path
from aws_cdk import App, Environment,Aws

# Add the project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# fmt: off
from infrastructure.cdk.stacks.application_stack import ApplicationStack  # noqa: E402
# fmt: on

app = App()

# Get environment from context (default to dev)
env_name = app.node.try_get_context("env") or "dev"

# Define environments
environments = {
    "dev": {"stack_name": "ApplicationStack-Dev", "region": "us-east-2"},
    "stage": {"stack_name": "ApplicationStack-Stage", "region": "us-east-2"},
    "prod": {"stack_name": "ApplicationStack-Prod", "region": "us-east-2"},
}

env_config = environments[env_name]

# Instantiate the CDK stack
ApplicationStack(
    app,
    env_config["stack_name"],
    env=Environment(
        account=app.node.try_get_context("account") or Aws.ACCOUNT_ID, # Pass via context when deploying
        region=env_config["region"]
    ),
    env_name=env_name,
)

app.synth()
# 217968404084
# cdk deploy --context env=dev --context account=217968404084

