#!/usr/bin/env python3
import os
from aws_cdk import App, Environment

from ik_hxr_cms_backend.ik_hxr_cms_backend_stack import IkHxrCmsBackendStack

app = App()

env_name = app.node.try_get_context('env') or 'dev'

environments = {
    'dev': {
        'stack_name': 'IkHxrCmsBackendStack-Dev',
        'region': 'us-east-2'
    },
    'stage': {
        'stack_name': 'IkHxrCmsBackendStack-Stage',
        'region': 'us-east-2'
    },
    'prod': {
        'stack_name': 'IkHxrCmsBackendStack-Prod',
        'region': 'us-east-2'
    }
}

env_config = environments[env_name]


IkHxrCmsBackendStack(app, env_config['stack_name'],
    env=Environment(
        account=app.node.try_get_context('account'),
        region=env_config['region']
    ),
    env_name=env_name
)

app.synth()
