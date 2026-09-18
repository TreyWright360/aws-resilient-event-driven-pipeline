import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Secondary Consumer Lambda demonstrating SNS Fan-Out Architecture.
    Processes S3 audit events independently from the ETL pipeline.
    """
    for record in event.get('Records', []):
        try:
            body = json.loads(record['body'])
            message = json.loads(body.get('Message', '{}')) if "Message" in body else body
            
            logger.info(f"Audit log recorded for event: {json.dumps(message)}")
            
        except Exception as e:
            logger.error(f"Failed to parse audit event: {e}")
            
    return {"statusCode": 200, "body": "Audit processed"}
