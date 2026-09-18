# Resilient Multi-Consumer Event-Driven Ingestion Pipeline (AWS)

[![Terraform](https://img.shields.io/badge/IaC-Terraform_v1.5+-623CE4.svg?logo=terraform)](https://www.terraform.io)
[![AWS](https://img.shields.io/badge/Cloud-AWS_Serverless-FF9900.svg?logo=amazon-aws)](https://aws.amazon.com)
[![Python](https://img.shields.io/badge/Language-Python_3.12-3776AB.svg?logo=python)](https://www.python.org)

An enterprise-grade, serverless data ingestion architecture designed for high reliability, fault tolerance, and zero data loss on AWS. Built with **Infrastructure as Code (Terraform)**, this project demonstrates how to resolve critical distributed system failure modes including **SQS retry storms**, **SNS-SQS resource trust boundaries**, **batch poisoning**, and **Lambda memory exhaustion**.

---

## 📐 Architecture Overview

```
                      ┌──────────────────────────────────────────────────────────┐
                      │                   Amazon S3 Bucket                       │
                      │               (Landing: /sourcefile/)                    │
                      └────────────────────────────┬─────────────────────────────┘
                                                   │ S3 ObjectCreated Event
                                                   ▼
                                      ┌─────────────────────────┐
                                      │     Amazon SNS Topic    │
                                      │ (s3-events-broadcast)   │
                                      └────────────┬────────────┘
                        ┌──────────────────────────┴──────────────────────────┐
                        │ Fan-Out                                             │ Fan-Out
                        ▼                                                     ▼
       ┌───────────────────────────────────┐                 ┌─────────────────────────────────┐
       │       Primary SQS Queue           │                 │      Audit Log SQS Queue        │
       │   - Visibility Timeout: 60s       │                 │     (Separate consumer queue)   │
       │   - Resource Policy (SNS Allowed) │                 └────────────────┬────────────────┘
       └────────────────┬──────────────────┘                                  │
                        │                                                     ▼
                        ▼                                    ┌─────────────────────────────────┐
       ┌───────────────────────────────────┐                 │       Audit Logger Lambda       │
       │        ETL Processor Lambda       │                 └─────────────────────────────────┘
       │   - Partial batch failures        │
       │   - Zero-copy S3 server-side move │
       │   - URL-safe key decoding         │
       └────────────────┬──────────────────┘
                        │ Max Receives >= 3
                        ▼
       ┌───────────────────────────────────┐
       │      Dead-Letter Queue (DLQ)      │
       │   - Retention: 14 Days            │
       │   - CloudWatch Alarm (Depth > 0)  │
       └────────────────┬──────────────────┘
                        │
                        ▼
       ┌───────────────────────────────────┐
       │   CloudWatch Alarms & Redrive     │
       └───────────────────────────────────┘
```

---

## 🚀 Key Engineering Highlights

| Feature | Problem Solved | Production Implementation |
| :--- | :--- | :--- |
| **Dead-Letter Redrive Policy** | Infinite SQS retry storms & runaway Lambda invocations | Configured `maxReceiveCount = 3` with 14-day retention DLQ. |
| **Visibility Timeout Tuning** | Race conditions & duplicate worker processing | Tuned SQS `VisibilityTimeout` to $6\times$ Lambda function duration. |
| **Cross-Service Trust** | Silent message drop between SNS and SQS | SQS Resource Policy allowing `sns.amazonaws.com` with strict `SourceArn` check. |
| **Partial Batch Item Failures** | One malformed message failing entire batch of 10 | `ReportBatchItemFailures` returning only failing `itemIdentifier`s. |
| **Zero-Memory S3 Copy** | Lambda RAM crashes on large file payloads | Server-side `s3.copy_object` and URL-decoded key resolution. |
| **Least-Privilege Security** | Dangerous wildcard `*FullAccess` permissions | Scoped IAM roles with granular path-level S3 and SQS actions. |

---

## 📂 Repository Structure

```
├── terraform/                   # Infrastructure as Code (Terraform)
│   ├── main.tf                  # Complete AWS resource definitions
│   ├── variables.tf             # Configurable parameters (region, environment)
│   └── outputs.tf               # Exported ARNs, Queue URLs, and Bucket names
├── src/                         # Lambda Application Source Code
│   ├── etl_processor/           # Production ETL Lambda with batch error isolation
│   │   └── lambda_function.py
│   └── audit_logger/            # Secondary consumer demonstrating Fan-Out
│       └── lambda_function.py
├── scripts/                     # Testing & Operations Tooling
│   ├── simulate_pipeline.py     # CLI tool to test happy path & poison pills
│   └── redrive_dlq.py           # Utility to inspect and redrive dead letters
└── docs/                        # Deep-Dive Documentation
    ├── FAILURE_MODES_AND_RCA.md # Comprehensive Root Cause Analysis case study
    └── RESUME_BULLET_POINTS.md  # Resume bullets and STAR interview answers
```

---

## 🛠️ Quickstart & Deployment

### 1. Prerequisites
* [AWS CLI](https://aws.amazon.com/cli/) configured (`aws configure`)
* [Terraform v1.5+](https://www.terraform.io/downloads)
* Python 3.12+ with `boto3` (`pip install boto3`)

### 2. Deploy Infrastructure
```bash
cd terraform
terraform init
terraform plan
terraform apply -auto-approve
```

### 3. Run Pipeline Tests
Use the included CLI tool to simulate production workloads:

```bash
# Obtain resource names from Terraform outputs
BUCKET=$(terraform output -raw s3_bucket_name)
PRIMARY_QUEUE=$(terraform output -raw primary_queue_url)
DLQ_QUEUE=$(terraform output -raw primary_dlq_url)

# 1. Test Happy Path File Ingestion
python3 ../scripts/simulate_pipeline.py --bucket $BUCKET --action upload-valid

# 2. Test File With Special Characters & Spaces
python3 ../scripts/simulate_pipeline.py --bucket $BUCKET --action upload-special-chars

# 3. Simulate a Poison Pill (Triggers DLQ eviction after 3 retries)
python3 ../scripts/simulate_pipeline.py --primary-queue $PRIMARY_QUEUE --action poison-pill

# 4. Check Queue Status
python3 ../scripts/simulate_pipeline.py --primary-queue $PRIMARY_QUEUE --dlq-queue $DLQ_QUEUE --action check-status
```

### 4. Inspect & Redrive Dead Letters
```bash
# View failed payloads in DLQ
python3 ../scripts/redrive_dlq.py --dlq-queue $DLQ_QUEUE --primary-queue $PRIMARY_QUEUE

# Redrive messages back to Primary Queue once resolved
python3 ../scripts/redrive_dlq.py --dlq-queue $DLQ_QUEUE --primary-queue $PRIMARY_QUEUE --redrive
```

---

## 📖 Deep Dive & Interview Prep
* Read the **[Root Cause Analysis Case Study](docs/FAILURE_MODES_AND_RCA.md)** for detailed explanations of each failure mode.
* Review **[Resume & Interview Talking Points](docs/RESUME_BULLET_POINTS.md)** for STAR-method responses.
