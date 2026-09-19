# SRE Runbook 02: Dead-Letter Queue (DLQ) Drain, Inspection & Redrive

## 🚨 Scenario
* CloudWatch Metric Alarm triggers: `ApproximateNumberOfMessagesVisible > 0` on the DLQ.
* Upstream producer sent malformed payloads, or downstream database had a temporary outage.

---

## 🛠️ Step-by-Step Resolution Workflow

### Step 1: Snapshot and Backup DLQ Payloads
Before mutating or replaying messages, create a local immutable timestamped backup:
```bash
make dlq-backup
```
*Saves all raw messages, metadata, and timestamps to `backups/sqs_backup_<TIMESTAMP>.json`.*

---

### Step 2: Inspect the Failure Root Cause
Open the latest backup file or inspect via CLI:
```bash
python3 scripts/redrive_dlq.py --dlq-queue <DLQ_URL> --primary-queue <PRIMARY_URL>
```
*Identify if failure is due to schema corruption (e.g. missing fields, bad types) or transient network downtime.*

---

### Step 3: Deploy Hotfix & Redrive Messages
1. If the bug is in Lambda code, deploy the fix:
   ```bash
   make deploy
   ```
2. Re-inject the dead-letter messages back into the primary queue:
   ```bash
   make dlq-redrive
   ```
3. Confirm that the primary queue drains down to 0 and DLQ depth returns to 0.
