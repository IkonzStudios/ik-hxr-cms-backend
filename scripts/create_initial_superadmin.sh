#!/usr/bin/env bash
#
# Create the initial superadmin user by invoking the CreateInitialSuperadmin Lambda.
#
# Usage:
#   ./create_initial_superadmin.sh <environment> <password> [aws_profile]
#
# Arguments:
#   environment   One of: dev, stage, prod. Determines which stack's Lambda is invoked.
#   password      Superadmin password (required). Use a strong password.
#   aws_profile   Optional. AWS CLI profile name (e.g. ik). Use if credentials are under a named profile.
#
# Notes:
#   - Super admin email is fixed as: superadmin@ikonz.club
#   - First name and last name are set to "Super" and "Admin"
#   - Lambda name format: Cms-CreateInitialSuperadmin-{Environment} (e.g. Cms-CreateInitialSuperadmin-Dev)
#   - Region: ap-south-1 (all environments)
#
# Example:
#   ./create_initial_superadmin.sh dev 'MySecurePass123!'
#   ./create_initial_superadmin.sh dev 'MySecurePass123!' ik
#   ./create_initial_superadmin.sh stage 'AnotherSecurePass456!' ik
#

set -e

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <environment> <password> [aws_profile]"
  echo "  environment: dev | stage | prod"
  echo "  password:    superadmin password (required)"
  echo "  aws_profile: optional AWS CLI profile (e.g. ik)"
  echo ""
  echo "Example: $0 dev 'MySecurePass123!'"
  echo "Example: $0 dev 'MySecurePass123!' ik"
  exit 1
fi

ENV_RAW="$1"
PASSWORD="$2"
AWS_PROFILE_ARG="${3:-}"

# Normalize env to capitalized for Lambda function name (dev -> Dev, stage -> Stage, prod -> Prod)
# Use tr/awk for portability (macOS default bash does not support ${var,,} or ${var^})
ENV_LOWER=$(echo "$ENV_RAW" | tr '[:upper:]' '[:lower:]')
case "$ENV_LOWER" in
  dev|stage|prod) ;;
  *)
    echo "Error: environment must be one of: dev, stage, prod (got: $ENV_RAW)"
    exit 1
    ;;
esac
ENV_CAPITALIZED=$(echo "$ENV_LOWER" | awk '{print toupper(substr($0,1,1)) substr($0,2)}')

FUNCTION_NAME="Cms-CreateInitialSuperadmin-${ENV_CAPITALIZED}"
REGION="ap-south-1"

EMAIL="superadmin@ikonz.club"
FIRST_NAME="Super"
LAST_NAME="Admin"

# Body must be a JSON string (Lambda parses event.body with json.loads)
BODY_JSON=$(jq -n \
  --arg email "$EMAIL" \
  --arg first_name "$FIRST_NAME" \
  --arg last_name "$LAST_NAME" \
  --arg password "$PASSWORD" \
  '{email: $email, first_name: $first_name, last_name: $last_name, password: $password}')
PAYLOAD=$(jq -n --arg body "$BODY_JSON" '{body: $body}')

echo "Invoking $FUNCTION_NAME in $REGION (email: $EMAIL)..."
if [[ -n "$AWS_PROFILE_ARG" ]]; then
  aws lambda invoke \
    --profile "$AWS_PROFILE_ARG" \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION" \
    --payload "$PAYLOAD" \
    --cli-binary-format raw-in-base64-out \
    /tmp/create_superadmin_out.json
else
  aws lambda invoke \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION" \
    --payload "$PAYLOAD" \
    --cli-binary-format raw-in-base64-out \
    /tmp/create_superadmin_out.json
fi

echo ""
echo "Response:"
cat /tmp/create_superadmin_out.json | jq .
echo ""

STATUS=$(jq -r '.statusCode // empty' /tmp/create_superadmin_out.json)
if [[ "$STATUS" == "201" ]]; then
  echo "Superadmin created successfully."
elif [[ "$STATUS" == "409" ]]; then
  echo "Superadmin user already exists."
  exit 0
else
  echo "Request failed (status: $STATUS). Check the response above."
  exit 1
fi
