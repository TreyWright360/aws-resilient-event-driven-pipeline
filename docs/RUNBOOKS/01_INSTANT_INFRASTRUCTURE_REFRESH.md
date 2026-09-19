# SRE Runbook 01: Instant Infrastructure Refresh & Rapid Rebuild

## 🚨 Scenario
* An accidental manual deletion occurred in the AWS Console (e.g. Lambda trigger removed, SQS queue deleted).
* A configuration drift occurred, causing unpredictable pipeline failures.
* Complete environment rebuild is needed in a fresh region or AWS account.

---

## ⏱️ Recovery Time Objective (RTO): < 3 Minutes

### Step 1: Health Diagnostics
Run the automated health check to identify what component is down:
```bash
make health-check
```
*Output will highlight exactly which component (`S3`, `SNS`, `SQS`, or `Lambda`) is returning `ERROR`.*

---

### Step 2: Instant Reconciliation (Non-Destructive)
If resources exist but settings drifted:
```bash
make refresh-quick
# OR
cd terraform && terraform apply -auto-approve
```
*Terraform will compare state against live AWS resources and automatically re-apply missing policies, triggers, and configurations.*

---

### Step 3: Complete Disaster Recovery (Full Rebuild)
If the infrastructure is corrupted and must be completely recreated:
```bash
# 1. Tear down any broken artifacts (optional)
make destroy

# 2. Deploy fresh, certified infrastructure
make init
make deploy

# 3. Verify end-to-end operational health
make health-check
make test-upload
```
