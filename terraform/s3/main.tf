# ──────────────────────────────────────────────────────────────
# FinSage – S3 Bucket for SEC Filing Document Storage
# ──────────────────────────────────────────────────────────────

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile
}

# ──────────────────────────────────────────────────────────────
# S3 Bucket
# ──────────────────────────────────────────────────────────────
resource "aws_s3_bucket" "finsage_filings" {
  bucket        = var.bucket_name
  force_destroy = false

  tags = {
    Project     = "FinSage"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# ──────────────────────────────────────────────────────────────
# Versioning — keep history of re-downloaded filings
# ──────────────────────────────────────────────────────────────
resource "aws_s3_bucket_versioning" "filings_versioning" {
  bucket = aws_s3_bucket.finsage_filings.id

  versioning_configuration {
    status = "Enabled"
  }
}

# ──────────────────────────────────────────────────────────────
# Server-side encryption (AES-256)
# ──────────────────────────────────────────────────────────────
resource "aws_s3_bucket_server_side_encryption_configuration" "filings_sse" {
  bucket = aws_s3_bucket.finsage_filings.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

# ──────────────────────────────────────────────────────────────
# Block all public access
# ──────────────────────────────────────────────────────────────
resource "aws_s3_bucket_public_access_block" "filings_public_block" {
  bucket = aws_s3_bucket.finsage_filings.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ──────────────────────────────────────────────────────────────
# Lifecycle rules
#   - Move raw filings to IA after 90 days
#   - Move extracted text to IA after 180 days
#   - Expire old non-current versions after 30 days
# ──────────────────────────────────────────────────────────────
resource "aws_s3_bucket_lifecycle_configuration" "filings_lifecycle" {
  bucket = aws_s3_bucket.finsage_filings.id

  rule {
    id     = "archive-raw-filings"
    status = "Enabled"

    filter {
      prefix = "filings/raw/"
    }

    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }
  }

  rule {
    id     = "archive-extracted-text"
    status = "Enabled"

    filter {
      prefix = "filings/extracted/"
    }

    transition {
      days          = 180
      storage_class = "STANDARD_IA"
    }
  }

  rule {
    id     = "cleanup-old-versions"
    status = "Enabled"

    filter {}

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

# ──────────────────────────────────────────────────────────────
# Seed the folder structure with zero-byte marker objects
# ──────────────────────────────────────────────────────────────
# Folder layout:
#   filings/raw/{ticker}/{form_type}/{accession_no}.html
#   filings/extracted/{ticker}/{form_type}/{accession_no}_mda.txt
#   filings/extracted/{ticker}/{form_type}/{accession_no}_risk.txt
#   filings/metadata/                (manifest / index JSON files)
# ──────────────────────────────────────────────────────────────

locals {
  folder_markers = [
    "filings/raw/",
    "filings/extracted/",
    "filings/metadata/",
  ]
}

resource "aws_s3_object" "folder_markers" {
  for_each = toset(local.folder_markers)

  bucket  = aws_s3_bucket.finsage_filings.id
  key     = each.value
  content = ""

  tags = {
    Purpose = "folder-marker"
  }
}

# ──────────────────────────────────────────────────────────────
# IAM Policy — scoped access for the FinSage application
# ──────────────────────────────────────────────────────────────
resource "aws_iam_policy" "finsage_s3_access" {
  name        = "finsage-s3-filings-access"
  description = "Allows FinSage app to read/write SEC filings in S3"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ListBucket"
        Effect = "Allow"
        Action = [
          "s3:ListBucket",
          "s3:GetBucketLocation"
        ]
        Resource = aws_s3_bucket.finsage_filings.arn
      },
      {
        Sid    = "ReadWriteObjects"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = "${aws_s3_bucket.finsage_filings.arn}/*"
      }
    ]
  })
}

# ──────────────────────────────────────────────────────────────
# IAM Policy — read-only access for Snowflake external stage
# ──────────────────────────────────────────────────────────────
resource "aws_iam_policy" "snowflake_s3_readonly" {
  name        = "finsage-snowflake-s3-readonly"
  description = "Read-only access for Snowflake external stage to read filing data"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ListFilingsBucket"
        Effect = "Allow"
        Action = [
          "s3:ListBucket",
          "s3:GetBucketLocation"
        ]
        Resource = aws_s3_bucket.finsage_filings.arn
        Condition = {
          StringLike = {
            "s3:prefix" = ["filings/extracted/*"]
          }
        }
      },
      {
        Sid    = "ReadExtractedText"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:GetObjectVersion"
        ]
        Resource = "${aws_s3_bucket.finsage_filings.arn}/filings/extracted/*"
      }
    ]
  })
}