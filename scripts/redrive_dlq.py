#!/usr/bin/env python3
"""
Utility script to inspect messages in the Dead-Letter Queue (DLQ)
and optionally redrive them back to the primary queue.
"""
import argparse
import json
import boto3

def inspect_and_redrive(dlq_url, target_queue_url, redrive=False):
    sqs = boto3.client('sqs')
    print(f"[*] Polling messages from DLQ: {dlq_url}...")
    
    response = sqs.receive_message(
        QueueUrl=dlq_url,
        MaxNumberOfMessages=10,
        VisibilityTimeout=30,
        WaitTimeSeconds=5
    )
    
    messages = response.get('Messages', [])
    if not messages:
        print("[i] DLQ is empty. No dead letters found.")
        return
        
    print(f"[!] Found {len(messages)} dead-letter message(s):")
    
    for idx, msg in enumerate(messages, 1):
        print(f"\n--- Message {idx} [ID: {msg['MessageId']}] ---")
        try:
            body = json.loads(msg['Body'])
            print(json.dumps(body, indent=2))
        except Exception:
            print(msg['Body'])
            
        if redrive:
            print(f"[*] Redriving message {msg['MessageId']} -> {target_queue_url}...")
            sqs.send_message(
                QueueUrl=target_queue_url,
                MessageBody=msg['Body']
            )
            print(f"[*] Deleting message from DLQ...")
            sqs.delete_message(
                QueueUrl=dlq_url,
                ReceiptHandle=msg['ReceiptHandle']
            )
            print("[✓] Redrive complete.")

def main():
    parser = argparse.ArgumentParser(description="Inspect and Redrive DLQ Messages")
    parser.add_argument("--dlq-queue", required=True, help="Dead-Letter Queue URL")
    parser.add_argument("--primary-queue", required=True, help="Target Primary Queue URL")
    parser.add_argument("--redrive", action="store_true", help="Move messages from DLQ back to primary queue")
    
    args = parser.parse_args()
    inspect_and_redrive(args.dlq_queue, args.primary_queue, args.redrive)

if __name__ == "__main__":
    main()
