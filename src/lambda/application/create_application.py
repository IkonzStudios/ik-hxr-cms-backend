import os
import json
import uuid
import boto3
import traceback
from datetime import datetime
# from utils.constants import STATUS_ACTIVE
from dotenv import load_dotenv
from utils.helpers import parse_request_body,validate_required_fields,create_application_data,save_application_to_db,create_success_response,create_error_response

load_dotenv()

dynamodb = boto3.resource('dynamodb')
table_name = os.environ.get("TABLE_NAME", "cms-applications")
table = dynamodb.Table(table_name)

def handler(event, context):
    """
    Lambda function to create a new application in DynamoDB.

    Expected event structure:
    {
        "name": "Application Name",
        "description": "Detailed description of the application",
        "author": "Author Name",
        "version": "1.0.0",
        "platform": "web | android | ios",
        "organization_id": "123e4567-e89b-12d3-a456-426614174000",
        "status": "active | inactive",
        "tags": "[\"media\", \"internal\", \"beta\"]",
        "release_date": "2025-06-20",
        "repository_url": "https://github.com/org/app-repo"
    }
    """

    try:
        # Get table name from environment variable
        table_name = os.environ.get("APPLICATION_TABLE_NAME")
        if not table_name:
            raise ValueError("APPLICATION_TABLE_NAME is not set in environment variables")

        # Debug: Print the event structure for development
        print("Received event:", json.dumps(event))

        # Parse request body
        body, parse_error = parse_request_body(event)
        if parse_error:
            return parse_error

        # Validate required fields
        # if "name" not in body or "author" not in body:
        #     raise ValueError("Missing required fields: 'name' or 'author'")

        validation_error = validate_required_fields(body)
        if validation_error:
            return validation_error

        # Create application data (adds id, timestamps, etc.)
        application_data = create_application_data(body)

        # Save to database
        save_error = save_application_to_db(application_data, table_name)
        if save_error:
            return save_error

        # Return success response
        return create_success_response("Application created successfully", application_data)

    except ValueError as e:
        return create_error_response(400, str(e))

    except Exception as e:
        print(f"Error creating application: {str(e)}")
        print(f"Error type: {type(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return create_error_response(500, "Internal server error")
