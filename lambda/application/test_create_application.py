from create_application import handler

# Simulate Lambda event
event = {
    "body": '{"name": "My App", "author": "John", "status": "active"}'
}

# Simulate context (can be empty for testing)
context = {}

# Call the Lambda function
response = handler(event, context)

# Print the output
print(response)