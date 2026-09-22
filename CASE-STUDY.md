# Case study: resilient event pipeline concept

**Portfolio status:** Concept only. The repository currently has no Terraform, processor, tests, AWS deployment, or failure evidence.

## Business problem

Model a pipeline that accepts an event, isolates consumer failures, and safely replays messages without duplicating downstream effects.

## Intended architecture and technologies

The planned design is S3 → SNS → SQS → Lambda with a dead-letter queue, partial batch failure response, and idempotency key. None of these components is implemented in this repository yet.

## Failure modes and runbooks

The [handbook content index](https://github.com/TreyWright360/aws-cloud-operations-handbook/blob/main/CONTENT-INDEX.md) tracks the future failure-and-replay episode. The lab should inject a malformed event, observe retries and DLQ arrival, correct the consumer, replay once, and verify the downstream record.

## Test evidence and video

**DOCUMENTATION ONLY.** No test or video exists. This case study must remain labeled a design until code and dated proof are published.

## Security and cost controls

The future implementation should scope S3/SNS/SQS/Lambda IAM actions, encrypt queues and buckets, set retention and DLQ age alarms, and set a lab budget. No deployed controls can be claimed today.

## Production improvements

After implementation, add idempotency storage, poison-message handling, redrive authorization, observability, replay rate limits, and a documented recovery procedure.
