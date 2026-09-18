# Resume Bullet Points & Interview Talking Points

Use these tailored bullet points and interview talking points to showcase this project on your Data Engineering / Cloud Engineering resume.

---

## 📄 Bullet Points for Resume / LinkedIn

### Option 1: Focus on Data Engineering & Pipeline Resilience
> * **Resilient Event-Driven Data Pipeline (AWS / Terraform):** Architected a serverless S3 $\rightarrow$ SNS $\rightarrow$ SQS $\rightarrow$ Lambda data ingestion pipeline featuring fan-out distribution, dead-letter redrive queues (DLQ), and automated CloudWatch alarms. Eliminated retry storms and isolated poisoned records using SQS `ReportBatchItemFailures` and zero-memory server-side S3 object management.

### Option 2: Focus on Cloud Architecture & Infrastructure as Code (IaC)
> * **AWS Serverless Infrastructure & Observability (Terraform / Python):** Engineered an asynchronous event-driven landing zone with multi-consumer fan-out architecture. Implemented least-privilege IAM and resource-based SQS access policies, tuned visibility timeouts ($6\times$ invocation threshold), and built automated DLQ redrive tooling to guarantee zero message loss.

---

## 🎯 STAR Format Interview Preparation

### Situation
> "In high-throughput event-driven data ingestion architectures on AWS, unhandled exceptions and poison-pill records can trigger infinite retry storms, exhausting Lambda concurrency, inflating cloud costs, and silently dropping critical data."

### Task
> "I designed and deployed an enterprise-grade, resilient S3 $\rightarrow$ SNS $\rightarrow$ SQS $\rightarrow$ Lambda pipeline using Terraform to guarantee deterministic error isolation, prevent retry loops, and enable multi-consumer fan-out without data loss."

### Action
> 1. **Architectural Decoupling:** Implemented an S3 $\rightarrow$ SNS $\rightarrow$ SQS fan-out pattern with resource-based queue policies scoped with strict `aws:SourceArn` conditions.
> 2. **Dead-Letter Strategy:** Configured SQS redrive policies with `maxReceiveCount = 3` and tuned queue visibility timeouts to $6\times$ Lambda execution duration to eliminate race conditions.
> 3. **Batch Failure Isolation:** Enabled `ReportBatchItemFailures` in Lambda to prevent poison pills from forcing the entire batch into re-processing.
> 4. **Resource Optimization:** Replaced memory-heavy file streaming with server-side `copy_object` and URL-decoded S3 key handlers.
> 5. **Observability & Recovery:** Configured CloudWatch metric alarms for DLQ depth and built automated Python CLI tools to inspect and redrive dead-letter messages.

### Result
> "Created a self-healing ingestion pipeline that isolates corrupt messages within 3 retries, triggers real-time alerts, protects downstream consumers from batch poisoning, and scales serverlessly with zero memory overhead."
