# SRE Runbook 04: S3 Data Lake Backup, Versioning & Fast Restore

## 🚨 Scenario
* Accidental deletion or overwrite of raw landing files in S3.
* Data corruption in output partitions requiring replay from raw bronze storage.

---

## 🛡️ Production Backup Safeguards

### 1. Enable S3 Versioning & Object Lock
In production environments, ensure S3 bucket versioning is enabled to prevent permanent data deletion:
```hcl
resource "aws_s3_bucket_versioning" "versioning" {
  bucket = aws_s3_bucket.data_lake.id
  versioning_configuration {
    status = "Enabled"
  }
}
```

### 2. Fast Reprocessing Workflow
To re-run the entire pipeline for a specific day or dataset:
1. Re-upload or sync files from cold backup storage into `s3://<BUCKET>/sourcefile/`.
2. S3 ObjectCreated events will automatically fire, broadcast through SNS, buffer in SQS, and re-populate `targetfile/` with zero human intervention.
3. Check status:
   ```bash
   make health-check
   ```
