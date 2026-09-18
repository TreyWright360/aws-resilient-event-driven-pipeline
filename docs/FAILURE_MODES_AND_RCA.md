# Engineering Case Study: Failure Modes & Root Cause Analysis (RCA)

This document provides a deep dive into the three distributed systems failure modes encountered in event-driven AWS architectures, why they happen under the hood, and how this architecture resolves them.

---

## Failure Mode 1: SQS Infinite Retry Loops & Lack of DLQ Visibility

### Symptoms
* A Lambda function fails during execution (e.g. malformed JSON, unhandled exception).
* CloudWatch logs show the same message ID executing repeatedly every few seconds.
* SQS queue depth does not decrease; no failed message reaches a dead-letter queue.
* CloudWatch metrics indicate exploding Lambda invocations and growing AWS bill.

### Root Cause Under the Hood
1. **Lambda Event Source Mapping (ESM):** Lambda polls SQS on behalf of the function.
2. **Message Acknowledgement:** Messages are only deleted from SQS when the Lambda function exits with a `200 OK` (or without throwing an unhandled exception).
3. **Visibility Timeout Expiry:** When the Lambda function crashes, the message remains unacknowledged in SQS. Once the queue's `VisibilityTimeout` elapses, the message transitions from *in-flight* (`ApproximateNumberOfMessagesNotVisible`) back to *visible* (`ApproximateNumberOfMessages`).
4. **Missing Redrive Policy:** Without a configured `RedrivePolicy` specifying a `deadLetterTargetArn` and `maxReceiveCount`, SQS has no threshold for eviction. The message will cycle infinitely until the `MessageRetentionPeriod` (up to 14 days) purges it.

### The Production Fix
* Attach a **Dead-Letter Queue (DLQ)** with maximum retention (14 days).
* Set `maxReceiveCount = 3` on the primary queue's redrive policy.
* Ensure the Primary Queue's `VisibilityTimeout >= 6 * LambdaTimeout` (e.g. 60s for a 10s Lambda) to prevent race conditions where a message becomes visible to another worker before the first worker finishes.
* Configure a **CloudWatch Metric Alarm** on `ApproximateNumberOfMessagesVisible > 0` for the DLQ to notify on-call engineers.

---

## Failure Mode 2: SNS-to-SQS Silent Message Drops (Resource-Based Trust)

### Symptoms
* S3 files are uploaded successfully and S3 triggers the SNS Topic.
* SNS CloudWatch metrics show `NumberOfMessagesPublished = 1` and `NumberOfNotificationsDelivered = 0` (or `NumberOfNotificationsFailed = 1`).
* SQS queue remains completely empty.
* Lambda consumer has zero invocations and zero log streams.

### Root Cause Under the Hood
* IAM security in AWS is evaluated across two policy types: **Identity-Based Policies** (attached to IAM Roles/Users) and **Resource-Based Policies** (attached to SQS, S3, KMS).
* When SNS pushes a message to SQS, SNS acts as a service principal (`sns.amazonaws.com`).
* SQS queues are private by default. Without an explicit **SQS Access Policy** permitting `sns.amazonaws.com` to call `sqs:SendMessage`, SQS silently denies the delivery attempts.

### The Production Fix
Attach an SQS Resource Policy restricting access strictly to the expected SNS Topic ARN:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowSNSToSendMessages",
      "Effect": "Allow",
      "Principal": { "Service": "sns.amazonaws.com" },
      "Action": "sqs:SendMessage",
      "Resource": "arn:aws:sqs:<REGION>:<ACCOUNT_ID>:<QUEUE_NAME>",
      "Condition": {
        "ArnEquals": {
          "aws:SourceArn": "arn:aws:sns:<REGION>:<ACCOUNT_ID>:<TOPIC_NAME>"
        }
      }
    }
  ]
}
```

---

## Failure Mode 3: Lambda Memory Exhaustion, Key Encoding, & Batch Poisoning

### Symptoms
* Large file uploads (>100MB) cause Lambda out-of-memory crashes (`Runtime.ExitError`).
* Files with spaces or symbols in names (e.g. `quarter 1 report.csv`) fail with `404 NoSuchKey`.
* A single malformed message in a batch of 10 causes all 10 messages to fail and re-process.

### Root Cause Under the Hood
1. **Streaming into RAM:** Using `s3.get_object()['Body'].read()` loads the entire file binary into Lambda RAM.
2. **S3 Event Key Encoding:** S3 event notifications URL-encode object keys (replacing spaces with `+` or `%20`).
3. **Batch All-or-Nothing Retries:** Standard SQS-Lambda integrations treat any unhandled exception as a failure of the *entire* batch, causing downstream duplicate processing of valid messages.

### The Production Fix
1. **Zero-Memory Server-Side S3 Copy:** Use `s3.copy_object(Bucket=..., CopySource=..., Key=...)`, which delegates the byte transfer entirely to S3 internal infrastructure.
2. **Key Decoding:** Decode object keys using `urllib.parse.unquote_plus(raw_key)`.
3. **Partial Batch Item Failures (`ReportBatchItemFailures`):**
   * Enable `function_response_types = ["ReportBatchItemFailures"]` in the Lambda Event Source Mapping.
   * Return `{"batchItemFailures": [{"itemIdentifier": failed_id}]}` to SQS so that only the failing item is retried/evicted to DLQ while successfully processed items are committed.
