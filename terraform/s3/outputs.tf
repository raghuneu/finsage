output "bucket_name" {
  description = "Name of the SEC filings S3 bucket"
  value       = aws_s3_bucket.finsage_filings.id
}

output "bucket_arn" {
  description = "ARN of the SEC filings S3 bucket"
  value       = aws_s3_bucket.finsage_filings.arn
}

output "bucket_region" {
  description = "Region of the S3 bucket"
  value       = aws_s3_bucket.finsage_filings.region
}

output "app_policy_arn" {
  description = "IAM policy ARN for FinSage app access"
  value       = aws_iam_policy.finsage_s3_access.arn
}

output "snowflake_policy_arn" {
  description = "IAM policy ARN for Snowflake external stage read-only access"
  value       = aws_iam_policy.snowflake_s3_readonly.arn
}
