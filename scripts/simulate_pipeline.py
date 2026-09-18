#!/usr/bin/env python3
"""
CLI tool to test and simulate failure modes against the resilient event-driven pipeline.
"""
import argparse
import json
import time
import boto3

def upload_test_file(s3_client, bucket_name, file_name, content):
    key = f"sourcefile/{file_name}"
    print(f"[*] Uploading test file to s3://{bucket_name}/{key}...")
    s3_client.put_object(
        Bucket=bucket_name,
        Key=key,
        Body=content.encode('utf-8')
    )
    print(f"[✓] Upload successful: s3://{bucket_name}/{key}")

def send_poison_pill_to_sqs(sqs_client, queue_url):
    print(f"[*] Sending poison pill message to SQS: {queue_url}...")
    message_body = {
        "taskId": "T-1001",
        "description": "Simulated malformed message to test DLQ eviction",
        "timestamp": time.time()
    }
    response = sqs_client.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps(message_body)
    )
    print(f"[✓] Poison pill dispatched. MessageId: {response['MessageId']}")

def check_queue_depths(sqs_client, primary_url, dlq_url):
    print("\n[*] Polling Queue Message Counts...")
    attrs = ['ApproximateNumberOfMessages', 'ApproximateNumberOfMessagesNotVisible']
    
    primary_res = sqs_client.get_queue_attributes(QueueUrl=primary_url, AttributeNames=attrs)['Attributes']
    dlq_res = sqs_client.get_queue_attributes(QueueUrl=dlq_url, AttributeNames=attrs)['Attributes']
    
    print(f" - Primary Queue: {primary_res.get('ApproximateNumberOfMessages')} visible, {primary_res.get('ApproximateNumberOfMessagesNotVisible')} in-flight")
    print(f" - Dead-Letter Queue (DLQ): {dlq_res.get('ApproximateNumberOfMessages')} visible, {dlq_res.get('ApproximateNumberOfMessagesNotVisible')} in-flight")

def main():
    parser = argparse.ArgumentParser(description="Test and simulate pipeline scenarios")
    parser.add_argument("--bucket", help="Target S3 Bucket Name")
    parser.add_argument("--primary-queue", help="Primary SQS Queue URL")
    parser.add_argument("--dlq-queue", help="Dead-Letter Queue URL")
    parser.add_argument("--action", choices=["upload-valid", "upload-special-chars", "poison-pill", "check-status"], required=True)
    
    args = parser.parse_args()
    session = boto3.Session()
    s3 = session.client('s3')
    sqs = session.client('sqs')
    
    if args.action == "upload-valid":
        if not args.bucket:
            parser.error("--bucket required for upload-valid")
        upload_test_file(s3, args.bucket, "sample_orders.csv", "id,product,amount\n101,WidgetA,29.99\n102,WidgetB,49.50")
        
    elif args.action == "upload-special-chars":
        if not args.bucket:
            parser.error("--bucket required for upload-special-chars")
        upload_test_file(s3, args.bucket, "customer report 2026 #1.txt", "Sample report with spaces and special characters.")
        
    elif args.action == "poison-pill":
        if not args.primary_queue:
            parser.error("--primary-queue required for poison-pill")
        send_poison_pill_to_sqs(sqs, args.primary_queue)
        
    elif args.action == "check-status":
        if not args.primary_queue or not args.dlq_queue:
            parser.error("--primary-queue and --dlq-queue required for check-status")
        check_queue_depths(sqs, args.primary_queue, args.dlq_queue)

if __name__ == "__main__":
    main()
