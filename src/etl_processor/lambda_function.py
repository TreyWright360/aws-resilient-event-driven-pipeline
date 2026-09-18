import json
import logging
import urllib.parse
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client('s3')

def lambda_handler(event, context):
    """
    Production-ready SQS Consumer Lambda for S3 event-driven file processing.
    
    Key Engineering Features:
    1. Partial Batch Failure Reporting: Only failed message IDs are returned to SQS
       so valid messages in the batch are committed and not reprocessed.
    2. URL-Safe S3 Key Parsing: Decodes URL-encoded keys (e.g., spaces converted to '+').
    3. Memory-Efficient Server-Side S3 Copy: Avoids streaming large byte payloads into RAM.
    4. Poison Pill Detection & Safe Logging.
    """
    batch_item_failures = []
    
    for record in event.get('Records', []):
        message_id = record['messageId']
        
        try:
            logger.info(f"Processing SQS message ID: {message_id}")
            
            # SQS payload might be direct or wrapped inside an SNS notification
            body_raw = record['body']
            body_json = json.loads(body_raw)
            
            # Handle SNS-wrapped message structure
            if "Type" in body_json and body_json.get("Type") == "Notification":
                sns_message = json.loads(body_json['Message'])
            else:
                sns_message = body_json
            
            # Check for simulated poison pill payload
            if sns_message.get("taskId") == "T-1001" or sns_message.get("simulate_error") is True:
                raise ValueError(f"Poison pill detected in message {message_id}: {sns_message}")
            
            # Process S3 Event Records if present
            s3_records = sns_message.get('Records', [])
            if not s3_records:
                logger.warning(f"No S3 records found in message {message_id}. Raw payload: {sns_message}")
                continue
                
            for s3_event in s3_records:
                bucket_name = s3_event['s3']['bucket']['name']
                raw_key = s3_event['s3']['object']['key']
                object_key = urllib.parse.unquote_plus(raw_key)
                
                # Prevent recursive loop by verifying prefix
                if not object_key.startswith('sourcefile/'):
                    logger.info(f"Skipping object outside sourcefile/ prefix: {object_key}")
                    continue
                
                target_key = object_key.replace('sourcefile/', 'targetfile/', 1)
                
                logger.info(f"Copying s3://{bucket_name}/{object_key} -> s3://{bucket_name}/{target_key}")
                
                # Server-side copy without loading file bytes into Lambda RAM
                s3.copy_object(
                    Bucket=bucket_name,
                    CopySource={'Bucket': bucket_name, 'Key': object_key},
                    Key=target_key,
                    MetadataDirective='COPY'
                )
                
                logger.info(f"Successfully copied to {target_key}")

        except Exception as err:
            logger.error(f"Failed to process message {message_id}: {str(err)}", exc_info=True)
            # Add message ID to batch item failures for SQS retries / DLQ routing
            batch_item_failures.append({"itemIdentifier": message_id})
            
    return {
        "batchItemFailures": batch_item_failures
    }
