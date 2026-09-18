output "s3_bucket_name" {
  description = "S3 Data Lake Bucket Name"
  value       = aws_s3_bucket.data_lake.id
}

output "sns_topic_arn" {
  description = "SNS Event Broadcast Topic ARN"
  value       = aws_sns_topic.s3_events.arn
}

output "primary_queue_url" {
  description = "Primary ETL SQS Queue URL"
  value       = aws_sqs_queue.primary_queue.id
}

output "primary_dlq_url" {
  description = "Dead-Letter Queue URL"
  value       = aws_sqs_queue.primary_dlq.id
}

output "audit_queue_url" {
  description = "Audit SQS Queue URL"
  value       = aws_sqs_queue.audit_queue.id
}

output "etl_lambda_name" {
  description = "ETL Processor Lambda Name"
  value       = aws_lambda_function.etl_processor.function_name
}
