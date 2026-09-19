# SRE Runbook 03: Cross-Service IAM & Resource Policy Lockouts

## 🚨 Scenario
* S3 events or SNS messages are published successfully, but SQS has 0 messages, or Lambda fails with `AccessDeniedException`.

---

## 🔍 Diagnostic Checklist

### 1. SQS Access Policy Verification (SNS $\rightarrow$ SQS)
Ensure the queue has the resource policy allowing `sns.amazonaws.com`:
```json
{
  "Effect": "Allow",
  "Principal": { "Service": "sns.amazonaws.com" },
  "Action": "sqs:SendMessage",
  "Resource": "arn:aws:sqs:<REGION>:<ACCOUNT>:<QUEUE>",
  "Condition": {
    "ArnEquals": {
      "aws:SourceArn": "arn:aws:sns:<REGION>:<ACCOUNT>:<TOPIC>"
    }
  }
}
```

### 2. Lambda IAM Execution Role Scoping
Ensure the Lambda role has:
* `sqs:ReceiveMessage`, `sqs:DeleteMessage`, `sqs:GetQueueAttributes` on the specific queue ARN.
* `s3:GetObject` on `arn:aws:s3:::bucket/sourcefile/*`
* `s3:PutObject` on `arn:aws:s3:::bucket/targetfile/*`

### 3. Instant Automated Repair
To force re-apply the certified least-privilege policies:
```bash
make refresh-quick
```
