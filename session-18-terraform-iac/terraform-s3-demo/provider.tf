terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = "Session18-Terraform-S3-Demo"
      ManagedBy = "Terraform"
      Owner     = "Vivek Solanki"
    }
  }
}
