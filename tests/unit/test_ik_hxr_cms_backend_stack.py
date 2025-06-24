import aws_cdk as core
import aws_cdk.assertions as assertions

from ik_hxr_cms_backend.ik_hxr_cms_backend_stack import IkHxrCmsBackendStack

# example tests. To run these tests, uncomment this file along with the example
# resource in ik_hxr_cms_backend/ik_hxr_cms_backend_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = IkHxrCmsBackendStack(app, "ik-hxr-cms-backend")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
