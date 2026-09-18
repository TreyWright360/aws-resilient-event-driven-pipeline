terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

resource "random_id" "suffix" {
  byte_length = 4
}

locals {
  prefix = "${var.project_name}-${var.environment}-${random_id.suffix.hex}"
}

# =========================================================================
# 1. S3 Storage & Notification
# =========================================================================

resource "aws_s3_bucket" "data_lake" {
  bucket        = "${local.prefix}-data-lake"
  force_destroy = true
}

resource "aws_s3_bucket_notification" "s3_to_sns" {
  bucket = aws_s3_bucket.data_lake.id

  topic {
    topic_arn     = aws_sns_topic.s3_events.arn
    events        = ["s3:ObjectCreated:*"]
    filter_prefix = "sourcefile/"
  }

  depends_on = [aws_sns_topic_policy.s3_publish_policy]
}

# =========================================================================
# 2. SNS Broadcast Topic & Publish Policy
# =========================================================================

resource "aws_sns_topic" "s3_events" {
  name = "${local.prefix}-s3-events-topic"
}

resource "aws_sns_topic_policy" "s3_publish_policy" {
  arn = aws_sns_topic.s3_events.arn

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowS3ToPublish"
        Effect    = "Allow"
        Principal = { Service = "s3.amazonaws.com" }
        Action    = "sns:Publish"
        Resource  = aws_sns_topic.s3_events.arn
        Condition = {
          ArnEquals = {
            "aws:SourceArn" = aws_s3_bucket.data_lake.arn
          }
        }
      }
    ]
  })
}

# =========================================================================
# 3. SQS Queues: Dead-Letter Queue & Primary Processing Queue
# =========================================================================

# Dead-Letter Queue (DLQ)
resource "aws_sqs_queue" "primary_dlq" {
  name                      = "${local.prefix}-etl-dlq"
  message_retention_seconds = 1209600 # 14 days maximum retention for incident investigation
}

# Primary ETL SQS Queue
resource "aws_sqs_queue" "primary_queue" {
  name                       = "${local.prefix}-etl-queue"
  visibility_timeout_seconds = 60      # >= 6x Lambda timeout (Lambda timeout = 10s)
  message_retention_seconds  = 345600  # 4 days

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.primary_dlq.arn
    maxReceiveCount     = 3
  })
}

# SQS Resource Policy allowing SNS to push messages
resource "aws_sqs_queue_policy" "primary_queue_policy" {
  queue_url = aws_sqs_queue.primary_queue.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowSNSToSendMessages"
        Effect    = "Allow"
        Principal = { Service = "sns.amazonaws.com" }
        Action    = "sqs:SendMessage"
        Resource  = aws_sqs_queue.primary_queue.arn
        Condition = {
          ArnEquals = {
            "aws:SourceArn" = aws_sns_topic.s3_events.arn
          }
        }
      }
    ]
  })
}

# SQS Subscription to SNS Topic
resource "aws_sns_topic_subscription" "etl_queue_sub" {
  topic_arn            = aws_sns_topic.s3_events.arn
  protocol             = "sqs"
  endpoint             = aws_sqs_queue.primary_queue.arn
  raw_message_delivery = false
}

# Secondary Consumer: Audit Queue
resource "aws_sqs_queue" "audit_queue" {
  name                       = "${local.prefix}-audit-queue"
  visibility_timeout_seconds = 30
}

resource "aws_sqs_queue_policy" "audit_queue_policy" {
  queue_url = aws_sqs_queue.audit_queue.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowSNSToSendMessagesToAudit"
        Effect    = "Allow"
        Principal = { Service = "sns.amazonaws.com" }
        Action    = "sqs:SendMessage"
        Resource  = aws_sqs_queue.audit_queue.arn
        Condition = {
          ArnEquals = {
            "aws:SourceArn" = aws_sns_topic.s3_events.arn
          }
        }
      }
    ]
  })
}

resource "aws_sns_topic_subscription" "audit_queue_sub" {
  topic_arn = aws_sns_topic.s3_events.arn
  protocol  = "sqs"
  endpoint  = aws_sqs_queue.audit_queue.arn
}

# =========================================================================
# 4. IAM Roles with Least Privilege
# =========================================================================

resource "aws_iam_role" "lambda_etl_role" {
  name = "${local.prefix}-lambda-etl-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action    = "sts:AssumeRole"
        Effect    = "Allow"
        Principal = { Service = "lambda.amazonaws.com" }
      }
    ]
  })
}

resource "aws_iam_policy" "lambda_etl_policy" {
  name        = "${local.prefix}-lambda-etl-policy"
  description = "Least privilege policy for ETL Lambda processor"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # CloudWatch Logging
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      # SQS Read & Delete Operations
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = aws_sqs_queue.primary_queue.arn
      },
      # S3 Scoped Operations (Read sourcefile, Write targetfile)
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject"
        ]
        Resource = "${aws_s3_bucket.data_lake.arn}/sourcefile/*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject"
        ]
        Resource = "${aws_s3_bucket.data_lake.arn}/targetfile/*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "etl_attach" {
  role       = aws_iam_role.lambda_etl_role.name
  policy_arn = aws_iam_policy.lambda_etl_policy.arn
}

# Audit Lambda Role
resource "aws_iam_role" "lambda_audit_role" {
  name = "${local.prefix}-lambda-audit-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action    = "sts:AssumeRole"
        Effect    = "Allow"
        Principal = { Service = "lambda.amazonaws.com" }
      }
    ]
  })
}

resource "aws_iam_policy" "lambda_audit_policy" {
  name = "${local.prefix}-lambda-audit-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = aws_sqs_queue.audit_queue.arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "audit_attach" {
  role       = aws_iam_role.lambda_audit_role.name
  policy_arn = aws_iam_policy.lambda_audit_policy.arn
}

# =========================================================================
# 5. Lambda Packaging & Deployment
# =========================================================================

data "archive_file" "etl_zip" {
  type        = "zip"
  source_file = "${path.module}/../src/etl_processor/lambda_function.py"
  output_path = "${path.module}/../src/etl_processor/lambda.zip"
}

resource "aws_lambda_function" "etl_processor" {
  function_name    = "${local.prefix}-etl-processor"
  runtime          = "python3.12"
  handler          = "lambda_function.lambda_handler"
  role             = aws_iam_role.lambda_etl_role.arn
  filename         = data.archive_file.etl_zip.output_path
  source_code_hash = data.archive_file.etl_zip.output_base64sha256
  timeout          = 10
  memory_size      = 256
}

# Event Source Mapping with Partial Batch Failure Reporting
resource "aws_lambda_event_source_mapping" "sqs_etl_trigger" {
  event_source_arn                   = aws_sqs_queue.primary_queue.arn
  function_name                      = aws_lambda_function.etl_processor.arn
  batch_size                         = 10
  maximum_batching_window_in_seconds = 5
  function_response_types            = ["ReportBatchItemFailures"]
}

data "archive_file" "audit_zip" {
  type        = "zip"
  source_file = "${path.module}/../src/audit_logger/lambda_function.py"
  output_path = "${path.module}/../src/audit_logger/lambda.zip"
}

resource "aws_lambda_function" "audit_logger" {
  function_name    = "${local.prefix}-audit-logger"
  runtime          = "python3.12"
  handler          = "lambda_function.lambda_handler"
  role             = aws_iam_role.lambda_audit_role.arn
  filename         = data.archive_file.audit_zip.output_path
  source_code_hash = data.archive_file.audit_zip.output_base64sha256
  timeout          = 5
  memory_size      = 128
}

resource "aws_lambda_event_source_mapping" "sqs_audit_trigger" {
  event_source_arn = aws_sqs_queue.audit_queue.arn
  function_name    = aws_lambda_function.audit_logger.arn
  batch_size       = 5
}

# =========================================================================
# 6. Observability: CloudWatch Metric Alarm for DLQ Monitoring
# =========================================================================

resource "aws_cloudwatch_metric_alarm" "dlq_alarm" {
  alarm_name          = "${local.prefix}-dlq-message-alarm"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "Alarm triggered when dead-letter queue contains unhandled failed messages"

  dimensions = {
    QueueName = aws_sqs_queue.primary_dlq.name
  }
}
