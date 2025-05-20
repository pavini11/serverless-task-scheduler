import boto3
import os
import json
import requests

dynamodb = boto3.resource('dynamodb')
TABLE_NAME = os.environ['TABLE_NAME']

def lambda_handler(event, context):
    task_id = event.get('task_id')
    if not task_id:
        return {"statusCode": 400, "body": json.dumps({"error": "Missing task_id"})}

    table = dynamodb.Table(TABLE_NAME)
    response = table.get_item(Key={'task_id': task_id})
    task = response.get('Item')

    if not task:
        return {"statusCode": 404, "body": json.dumps({"error": "Task not found"})}

    try:
        if task['action'] == 'webhook':
            requests.post(task['payload']['url'], json=task['payload']['data'])
            task['status'] = 'completed'
        else:
            task['status'] = 'unknown_action'

    except Exception as e:
        task['status'] = 'failed'
        task['error'] = str(e)

    table.put_item(Item=task)

    return {"statusCode": 200, "body": json.dumps({"message": f"Task {task['status']}"})}
