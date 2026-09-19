# ==============================================================================
# AWS Resilient Pipeline: Disaster Recovery, Operations & Deployment Makefile
# ==============================================================================

.PHONY: help init deploy destroy refresh health-check test-upload test-poison dlq-backup dlq-redrive

help:
	@echo "Available commands for AWS Resilient Pipeline Management:"
	@echo "  make init          - Initialize Terraform workspace"
	@echo "  make deploy        - Deploy/refresh all infrastructure via Terraform"
	@echo "  make health-check  - Run automated health checks across S3, SNS, SQS, and Lambda"
	@echo "  make test-upload   - Simulate a valid file upload to S3"
	@echo "  make test-poison   - Inject a poison pill to test DLQ eviction"
	@echo "  make dlq-backup    - Snapshot and export dead-letter messages to a local JSON archive"
	@echo "  make dlq-redrive   - Inspect and redrive dead-letter messages back to primary queue"
	@echo "  make refresh-quick - Fast state refresh and reconciliation"
	@echo "  make destroy       - Tear down all AWS resources safely"

init:
	cd terraform && terraform init

deploy:
	cd terraform && terraform apply -auto-approve

refresh-quick:
	cd terraform && terraform apply -refresh-only -auto-approve

health-check:
	@cd terraform && \
	BUCKET=$$(terraform output -raw s3_bucket_name 2>/dev/null) && \
	TOPIC=$$(terraform output -raw sns_topic_arn 2>/dev/null) && \
	QUEUE=$$(terraform output -raw primary_queue_url 2>/dev/null) && \
	LAMBDA=$$(terraform output -raw etl_lambda_name 2>/dev/null) && \
	python3 ../scripts/disaster_recovery.py --action health-check --bucket $$BUCKET --topic $$TOPIC --queue $$QUEUE --lambda-name $$LAMBDA

test-upload:
	@cd terraform && \
	BUCKET=$$(terraform output -raw s3_bucket_name 2>/dev/null) && \
	python3 ../scripts/simulate_pipeline.py --bucket $$BUCKET --action upload-valid

test-poison:
	@cd terraform && \
	QUEUE=$$(terraform output -raw primary_queue_url 2>/dev/null) && \
	python3 ../scripts/simulate_pipeline.py --primary-queue $$QUEUE --action poison-pill

dlq-backup:
	@cd terraform && \
	DLQ=$$(terraform output -raw primary_dlq_url 2>/dev/null) && \
	python3 ../scripts/disaster_recovery.py --action backup-queue --queue $$DLQ

dlq-redrive:
	@cd terraform && \
	DLQ=$$(terraform output -raw primary_dlq_url 2>/dev/null) && \
	PRIMARY=$$(terraform output -raw primary_queue_url 2>/dev/null) && \
	python3 ../scripts/redrive_dlq.py --dlq-queue $$DLQ --primary-queue $$PRIMARY --redrive

destroy:
	cd terraform && terraform destroy -auto-approve
