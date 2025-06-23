from aws_cdk import aws_iam as iam


def create_ip_restriction_policy(env_name: str) -> iam.PolicyDocument:
    """
    Create an IP restriction policy for API Gateway that only allows access from specified IP address.

    Args:
        allowed_ip (str): The IP address in CIDR notation that should be allowed access.
                         Defaults to "3.111.114.251/32"

    Returns:
        iam.PolicyDocument: The policy document to be attached to API Gateway
    """
    if env_name == "dev":
        return None

    allowed_ips = ["3.111.114.251/32"]

    return iam.PolicyDocument(
        statements=[
            iam.PolicyStatement(
                sid="IPAllowOnly",
                effect=iam.Effect.DENY,
                principals=[iam.AnyPrincipal()],
                actions=["execute-api:Invoke"],
                resources=["*"],
                conditions={"NotIpAddress": {"aws:SourceIp": allowed_ips}},
            ),
            iam.PolicyStatement(
                sid="AllowSpecificIP",
                effect=iam.Effect.ALLOW,
                principals=[iam.AnyPrincipal()],
                actions=["execute-api:Invoke"],
                resources=["*"],
                conditions={"IpAddress": {"aws:SourceIp": allowed_ips}},
            ),
        ]
    )
