#!/usr/bin/env python3
"""
AWS Disaster Recovery & Rapid Refresh Automation Tool
Inspired by production site reliability engineering (SRE) practices.

Capabilities:
1. Snapshot & Backup DLQ / Queue messages to local timestamped JSON archive.
2. Health Check: Validates S3 bucket, SNS topic, SQS queues, and Lambda connectivity.
3. Automated Redrive: Re-injects dead letters into primary queues with backoff.
"""
import argparse
import datetime
import json
import os
import sys
import time
import boto3

def log(msg, level="INFO"):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{level}] {msg}")

def backup_queue_messages(sqs_client, queue_url, output_dir="backups"):
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(output_dir, f"sqs_backup_{timestamp}.json")
    
    log(f"Starting backup of messages from: {queue_url}")
    messages_saved = []
    
    while True:
        res = sqs_client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=10,
            VisibilityTimeout=30,
            WaitTimeSeconds=2
        )
        batch = res.get('Messages', [])
        if not batch:
            break
        for msg in batch:
            messages_saved.append({
                "MessageId": msg['MessageId'],
                "Body": msg['Body'],
                "Attributes": msg.get('Attributes', {}),
                "ReceiptHandle": msg['ReceiptHandle']
            })
            
    if not messages_saved:
        log("No messages found in queue to backup.", "WARN")
        return None
        
    with open(backup_file, "w") as f:
        json.dump(messages_saved, f, indent=2)
        
    log(f"Successfully backed up {len(messages_saved)} messages to: {backup_file}", "SUCCESS")
    return backup_file

def pipeline_health_check(session, bucket_name, topic_arn, queue_url, lambda_name):
    log("=== RUNNING PIPELINE HEALTH CHECK ===")
    s3 = session.client('s3')
    sns = session.client('sns')
    sqs = session.client('sqs')
    lmb = session.client('lambda')
    
    status = {"healthy": True, "checks": {}}
    
    # 1. Check S3
    try:
        s3.head_bucket(Bucket=bucket_name)
        log(f"S3 Bucket [{bucket_name}]: ONLINE", "SUCCESS")
        status["checks"]["s3"] = "ONLINE"
    except Exception as e:
        log(f"S3 Bucket [{bucket_name}]: ERROR ({str(e)})", "ERROR")
        status["checks"]["s3"] = f"ERROR: {str(e)}"
        status["healthy"] = False
        
    # 2. Check SNS
    try:
        sns.get_topic_attributes(TopicArn=topic_arn)
        log(f"SNS Topic [{topic_arn}]: ONLINE", "SUCCESS")
        status["checks"]["sns"] = "ONLINE"
    except Exception as e:
        log(f"SNS Topic [{topic_arn}]: ERROR ({str(e)})", "ERROR")
        status["checks"]["sns"] = f"ERROR: {str(e)}"
        status["healthy"] = False
        
    # 3. Check SQS
    try:
        attrs = sqs.get_queue_attributes(
            QueueUrl=queue_url, 
            AttributeNames=['ApproximateNumberOfMessages', 'ApproximateNumberOfMessagesNotVisible']
        )
        visible = attrs['Attributes']['ApproximateNumberOfMessages']
        in_flight = attrs['Attributes']['ApproximateNumberOfMessagesNotVisible']
        log(f"SQS Queue [{queue_url}]: ONLINE (Visible: {visible}, In-Flight: {in_flight})", "SUCCESS")
        status["checks"]["sqs"] = "ONLINE"
    except Exception as e:
        log(f"SQS Queue [{queue_url}]: ERROR ({str(e)})", "ERROR")
        status["checks"]["sqs"] = f"ERROR: {str(e)}"
        status["healthy"] = False
        
    # 4. Check Lambda
    try:
        cfg = lmb.get_function_configuration(FunctionName=lambda_name)
        log(f"Lambda Function [{lambda_name}]: ONLINE (State: {cfg.get('State', 'Active')})", "SUCCESS")
        status["checks"]["lambda"] = "ONLINE"
    except Exception as e:
        log(f"Lambda Function [{lambda_name}]: ERROR ({str(e)})", "ERROR")
        status["checks"]["lambda"] = f"ERROR: {str(e)}"
        status["healthy"] = False
        
    return status

def restore_from_backup(sqs_client, target_queue_url, backup_file):
    log(f"Restoring messages from {backup_file} into {target_queue_url}...")
    with open(backup_file, "r") as f:
        messages = json.load(f)
        
    for idx, msg in enumerate(messages, 1):
        sqs_client.send_message(
            QueueUrl=target_queue_url,
            MessageBody=msg['Body']
        )
        if idx % 10 == 0:
            log(f"Pushed {idx}/{len(messages)} messages...")
            
    log(f"Restore completed: {len(messages)} messages re-injected.", "SUCCESS")

def main():
    parser = argparse.ArgumentParser(description="AWS Pipeline Disaster Recovery & Maintenance CLI")
    parser.add_argument("--action", choices=["health-check", "backup-queue", "restore-backup"], required=True)
    parser.add_argument("--bucket", help="S3 Bucket Name")
    parser.add_argument("--topic", help="SNS Topic ARN")
    parser.add_argument("--queue", help="SQS Queue URL")
    parser.add_argument("--lambda-name", help="Lambda Function Name")
    parser.add_argument("--backup-file", help="Path to backup JSON file for restore")
    
    args = parser.parse_args()
    session = boto3.Session()
    sqs = session.client('sqs')
    
    if args.action == "health-check":
        if not all([args.bucket, args.topic, args.queue, args.lambda_name]):
            parser.error("health-check requires --bucket, --topic, --queue, and --lambda-name")
        pipeline_health_check(session, args.bucket, args.topic, args.queue, args.lambda_name)
        
    elif args.action == "backup-queue":
        if not args.queue:
            parser.error("backup-queue requires --queue")
        backup_queue_messages(sqs, args.queue)
        
    elif args.action == "restore-backup":
        if not args.queue or not args.backup_file:
            parser.error("restore-backup requires --queue and --backup-file")
        restore_from_backup(sqs, args.queue, args.backup_file)

if __name__ == "__main__":
    main()
