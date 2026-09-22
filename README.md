# Resilient event-driven pipeline

**Portfolio status:** Architecture concept. This repository currently contains a README only; Terraform, application code, tests, deployment, and failure-replay evidence are still to be added.

## Intended architecture

An S3 event fans out through SNS to SQS, where Lambda processes batches. A dead-letter queue and replay procedure will support failures, while idempotency will protect against duplicate delivery. These are design goals, not implemented capabilities in this repository yet.

## Recruiter-facing operational question

What happens when a consumer fails after the producer considers an event accepted? The planned lab will inject a malformed event, capture retries and DLQ behavior, fix the consumer, replay safely, and prove successful downstream processing.

The [AWS Cloud Operations Handbook](https://github.com/TreyWright360/aws-cloud-operations-handbook) contains the [22-point failure map](https://github.com/TreyWright360/aws-cloud-operations-handbook/blob/main/architecture/master-failure-map.md) and the evidence standard for this future exercise.

## Next implementation steps

1. Add Terraform for S3 notifications, SNS, SQS with DLQ, Lambda, IAM, and CloudWatch alarms.
2. Add a small processor with idempotency keys and partial batch failure handling.
3. Add automated tests and a bounded fault-injection script.
4. Capture a dated failure, DLQ redrive, and successful replay in the handbook evidence directory.
