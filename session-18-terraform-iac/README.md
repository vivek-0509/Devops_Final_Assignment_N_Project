# Session 18: Terraform & Infrastructure as Code

**Student:** Vivek Singh Solanki | **Roll number:** 24bcs10338

## Task 1: Terraform S3 demo
Full project and executed workflow (`init -> fmt -> validate -> plan -> apply -> show -> output -> destroy`) with outputs and screenshots: [terraform-s3-demo/README.md](terraform-s3-demo/README.md)

Quick summary of the run:

```bash
$ terraform apply -no-color -auto-approve tfplan
aws_s3_bucket.demo: Creating...
aws_s3_bucket.demo: Creation complete after 6s [id=vivek-devops-s3-demo-20261007-fa82aa]
aws_s3_bucket_versioning.demo: Creating...
aws_s3_object.readme: Creating...
aws_s3_bucket_public_access_block.demo: Creating...
aws_s3_bucket_server_side_encryption_configuration.demo: Creating...
aws_s3_object.readme: Creation complete after 2s [id=vivek-devops-s3-demo-20261007-fa82aa/hello.txt]
aws_s3_bucket_public_access_block.demo: Creation complete after 2s [id=vivek-devops-s3-demo-20261007-fa82aa]
aws_s3_bucket_server_side_encryption_configuration.demo: Creation complete after 2s [id=vivek-devops-s3-demo-20261007-fa82aa]
aws_s3_bucket_versioning.demo: Creation complete after 3s [id=vivek-devops-s3-demo-20261007-fa82aa]

Apply complete! Resources: 5 added, 0 changed, 0 destroyed.

Outputs:

bucket_arn = "arn:aws:s3:::vivek-devops-s3-demo-20261007-fa82aa"
bucket_domain_name = "vivek-devops-s3-demo-20261007-fa82aa.s3.amazonaws.com"
bucket_name = "vivek-devops-s3-demo-20261007-fa82aa"
bucket_region = "us-east-1"
versioning_status = "Enabled"
```

![apply](screenshots/03-apply-01.png)

## Task 2: AWS services research

| Service | Document |
|---|---|
| IAM (Governance) | [aws-services/01-iam/README.md](aws-services/01-iam/README.md) |
| EC2 (Compute) | [aws-services/02-ec2/README.md](aws-services/02-ec2/README.md) |
| S3 (Storage) | [aws-services/03-s3/README.md](aws-services/03-s3/README.md) |
| VPC (Networking) | [aws-services/04-vpc/README.md](aws-services/04-vpc/README.md) |
| DynamoDB & RDS (Databases) | [aws-services/05-dynamodb-rds/README.md](aws-services/05-dynamodb-rds/README.md) |

## Deliverables layout

```text
session-18-terraform-iac/
├── terraform-s3-demo/        main.tf, variables.tf, outputs.tf, provider.tf, terraform.tfvars, README.md
├── aws-services/
│   ├── 01-iam/README.md
│   ├── 02-ec2/README.md
│   ├── 03-s3/README.md
│   ├── 04-vpc/README.md
│   └── 05-dynamodb-rds/README.md
└── screenshots/
```
