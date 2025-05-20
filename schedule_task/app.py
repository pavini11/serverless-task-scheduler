import json
import boto3
import uuid
import os
from datetime import datetime

dynamodb = boto3.resource('dynamodb')
eventbridge = boto3.client('events')
lambda_client = boto3.client('lambda')

TABLE_NAME = os.environ['TABLE_NAME']
EXECUTE_LAMBDA_ARN = os.environ['EXECUTE_FUNCTION_ARN']

def is_cron_expression(s):
    return isinstance(s, str) and s.startswith('cron(') and s.endswith(')')

def convert_iso_to_cron(iso_str):
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    return f"cron({dt.minute} {dt.hour} {dt.day} {dt.month} ? {dt.year})"

def lambda_handler(event, context):
    body = json.loads(event.get('body', '{}'))

    task_id = str(uuid.uuid4())
    action = body.get('action')
    payload = body.get('payload')
    run_at = body.get('run_at')  # can be ISO8601 datetime or cron expression

    if not (action and payload and run_at):
        return {"statusCode": 400, "body": json.dumps({"error": "Missing fields"})}

    # Store task details in DynamoDB
    table = dynamodb.Table(TABLE_NAME)
    table.put_item(Item={
        'task_id': task_id,
        'action': action,
        'payload': payload,
        'run_at': run_at,
        'status': 'scheduled'
    })

    rule_name = f"task_{task_id}"

    # Determine ScheduleExpression
    if is_cron_expression(run_at):
        schedule_expression = run_at
    else:
        try:
            schedule_expression = convert_iso_to_cron(run_at)
        except Exception as e:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": f"Invalid run_at format: {str(e)}"})
            }

    # Create or update EventBridge rule with schedule expression
    eventbridge.put_rule(
        Name=rule_name,
        ScheduleExpression=schedule_expression,
        State='ENABLED'
    )

    # Add Lambda target to the rule
    eventbridge.put_targets(
        Rule=rule_name,
        Targets=[{
            'Id': '1',
            'Arn': EXECUTE_LAMBDA_ARN,
            'Input': json.dumps({'task_id': task_id})
        }]
    )

    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Task scheduled", "task_id": task_id, "schedule_expression": schedule_expression})
    }
