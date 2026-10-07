# AWS S3 - Simple Storage Service (Storage)

**Course:** DevOps - Session 18 (Terraform & Infrastructure as Code)
**Task 2:** AWS Services Research
**Author:** Vivek Singh Solanki (Roll No: 24bcs10338)

---

## What is S3?

Amazon Simple Storage Service (S3) is AWS's **object storage** service. You upload files (objects) into containers (buckets) and access them over HTTPS through the API, CLI, SDKs or the console. There is no disk to provision, no capacity to plan and no server to patch - S3 scales from one file to billions automatically.

Core characteristics:

- **Object storage, not a filesystem**: you store and retrieve whole objects by key. You cannot mount it like EBS and edit a file in place (although tools such as Mountpoint for S3 can present it as a filesystem for reading and sequential writes).
- **Durability of 99.999999999 % (11 nines)** - data is replicated across at least three Availability Zones for every storage class except One Zone classes.
- **Availability** of 99.99 % (Standard) with a published SLA.
- **Strong read-after-write consistency** for all operations - a `GET` immediately after a `PUT` or `DELETE` always returns the latest result.
- **Regional** service: a bucket is created in one region and data never leaves it unless you replicate it, but bucket **names** are globally unique.
- Pay only for what you use: storage per GB-month, requests, and data transfer out to the internet (transfer in is free).
- Practically unlimited capacity; the default quota is 10,000 general-purpose buckets per account (can be raised).

For this course S3 matters twice: as a resource we create with Terraform, and as the **remote backend** that stores Terraform's state file.

## Buckets

A bucket is the top-level container for objects. It belongs to one AWS account and one region.

Bucket naming rules (general-purpose buckets):

- 3 to 63 characters long.
- Only **lowercase letters, numbers, dots (.) and hyphens (-)**; must begin and end with a letter or number.
- Must **not** look like an IP address (`192.168.1.1`), start with `xn--` or `sthree-`, or end with `-s3alias` / `--ol-s3`.
- **Globally unique** across every AWS account in the partition - if anyone in the world owns `my-bucket`, you cannot create it. Hence names like `vivek-devops-tfstate-ap-south-1`.
- Avoid dots unless you need them (they break virtual-hosted-style HTTPS URLs because of certificate matching).
- Names cannot be changed after creation; you would create a new bucket and copy the data.

Each bucket has settings that apply to all objects inside: region, versioning, default encryption, Block Public Access, Object Ownership, lifecycle rules, logging, replication, tags and (optionally) a bucket policy.

Bucket URL formats:

```
https://<bucket>.s3.<region>.amazonaws.com/<key>      # virtual-hosted style (current default)
https://s3.<region>.amazonaws.com/<bucket>/<key>      # path style (legacy)
s3://<bucket>/<key>                                   # CLI / SDK shorthand
```

Note: AWS also offers **directory buckets** (S3 Express One Zone) for single-digit-millisecond access; they have a different naming scheme and are not covered further here.

## Objects

An object is the thing you actually store. It consists of:

| Part | Description |
|---|---|
| **Key** | The object's name, up to 1,024 bytes UTF-8, e.g. `logs/2026/10/07/app.log`. S3 has a **flat namespace** - the slashes are just characters, but the console and CLI treat the prefix (`logs/2026/10/07/`) as a folder. |
| **Value** | The data itself (any bytes). From **0 bytes to 5 TB** per object. A single `PUT` is limited to 5 GB; anything larger must use **multipart upload** (recommended above 100 MB - the CLI does this automatically). |
| **Metadata** | System metadata set by S3 (`Content-Length`, `Last-Modified`, `ETag`, storage class) plus optional user-defined `x-amz-meta-*` key/value pairs. Metadata is set at upload and cannot be edited in place - you copy the object over itself to change it. |
| **Version ID** | Present when versioning is enabled; identifies each version of the key. |
| **Tags** | Up to 10 key/value tags, usable in lifecycle rules, IAM conditions and cost allocation. |

Objects are identified by `bucket + key (+ version id)`. Operations are whole-object: `PutObject`, `GetObject`, `DeleteObject`, `CopyObject`, `HeadObject`, `ListObjectsV2`. There is no "append" - to change one byte you upload the whole object again.

## Storage classes

Storage classes trade **price per GB** against **retrieval cost, retrieval time and minimum storage duration**. The class is set per object (at upload, by lifecycle rule, or by changing it later).

| Storage class | Designed for | AZs | Min storage duration | Min billable size | Retrieval time | Approx. $/GB-month (us-east-1) |
|---|---|---|---|---|---|---|
| **S3 Standard** | Frequently accessed data | >= 3 | none | none | milliseconds | 0.023 |
| **S3 Intelligent-Tiering** | Unknown or changing access patterns | >= 3 | none | none (objects < 128 KB are never tiered and are charged at Standard rate without monitoring fee) | milliseconds (optional archive tiers: minutes-hours) | 0.023 -> 0.0125 -> 0.004 as it moves between tiers, plus a small per-object monitoring fee |
| **S3 Standard-IA** | Infrequent access, instant retrieval, long-lived data (backups, DR) | >= 3 | 30 days | 128 KB | milliseconds | 0.0125 + per-GB retrieval fee |
| **S3 One Zone-IA** | Re-creatable infrequent data; 20 % cheaper than Standard-IA | **1** | 30 days | 128 KB | milliseconds | 0.01 + retrieval fee |
| **S3 Glacier Instant Retrieval** | Archive that still needs millisecond access (medical images, media archives accessed once a quarter) | >= 3 | 90 days | 128 KB | milliseconds | 0.004 + retrieval fee |
| **S3 Glacier Flexible Retrieval** | Archives accessed 1-2 times a year | >= 3 | 90 days | 40 KB overhead | Expedited 1-5 min, Standard 3-5 h, Bulk 5-12 h (free) | 0.0036 |
| **S3 Glacier Deep Archive** | Long-term retention (7-10 years), compliance | >= 3 | 180 days | 40 KB overhead | Standard 12 h, Bulk 48 h | 0.00099 |

Notes:

- Deleting or overwriting an object before its minimum duration still charges for the full minimum period.
- The Glacier Flexible and Deep Archive classes require a **restore** request before the object can be read; the restored copy is temporary.
- Intelligent-Tiering moves objects automatically: 30 days without access -> Infrequent tier, 90 days -> Archive Instant tier; the opt-in Archive Access (90+ days) and Deep Archive Access (180+ days) tiers behave like Glacier. It is the safe default when you do not know the access pattern.
- One Zone-IA and S3 Express One Zone are the only classes that can lose data if an AZ is destroyed, so only use them for data you can regenerate.

## Versioning

Versioning keeps **every version of every object** in a bucket. It is a bucket-level setting with three states: *disabled* (default), *enabled*, *suspended* - once enabled it can never go back to disabled, only to suspended.

What changes when versioning is on:

- An overwrite creates a **new version** with a new version ID; the old one is kept and still billed.
- A `DELETE` without a version ID does not remove data - it inserts a **delete marker** that hides the object. Deleting the marker "undeletes" the object.
- To permanently remove data you must delete the specific version ID.
- **MFA Delete** can be enabled (root user, CLI only) to require an MFA code for permanent deletes or for changing the versioning state.

Versioning is required for S3 replication and strongly recommended for Terraform state buckets - when a bad `apply` corrupts the state you can roll back to the previous version.

```bash
aws s3api put-bucket-versioning --bucket vivek-devops-tfstate \
    --versioning-configuration Status=Enabled
aws s3api list-object-versions --bucket vivek-devops-tfstate --prefix session-18/
```

Pair versioning with a lifecycle rule that expires noncurrent versions, otherwise storage grows forever.

## Lifecycle policies

A lifecycle configuration is a set of rules that S3 applies automatically to objects matching a filter (prefix, tags, object size). Each rule can:

- **Transition** objects to a cheaper storage class after N days.
- **Expire** (delete) current objects after N days.
- Expire **noncurrent versions** after N days (or keep only the newest N).
- **Abort incomplete multipart uploads** after N days (these otherwise sit invisibly and cost money).
- Remove expired delete markers.

Constraints: objects must stay at least 30 days in Standard before a lifecycle transition to Standard-IA / One Zone-IA; transitions to Glacier classes can happen on day 0; transitions only go "downwards" in price.

Example rule in JSON (as used with `aws s3api put-bucket-lifecycle-configuration`):

```json
{
  "Rules": [
    {
      "ID": "logs-tiering-and-cleanup",
      "Status": "Enabled",
      "Filter": { "Prefix": "logs/" },
      "Transitions": [
        { "Days": 30,  "StorageClass": "STANDARD_IA" },
        { "Days": 90,  "StorageClass": "GLACIER_IR" },
        { "Days": 365, "StorageClass": "DEEP_ARCHIVE" }
      ],
      "Expiration": { "Days": 2555 },
      "NoncurrentVersionExpiration": { "NoncurrentDays": 30 },
      "AbortIncompleteMultipartUpload": { "DaysAfterInitiation": 7 }
    }
  ]
}
```

The same rule in Terraform:

```hcl
resource "aws_s3_bucket_lifecycle_configuration" "logs" {
  bucket = aws_s3_bucket.logs.id

  rule {
    id     = "logs-tiering-and-cleanup"
    status = "Enabled"

    filter {
      prefix = "logs/"
    }

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER_IR"
    }

    transition {
      days          = 365
      storage_class = "DEEP_ARCHIVE"
    }

    expiration {
      days = 2555 # ~7 years
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}
```

## Encryption

**At rest** - every new object in S3 has been encrypted by default since January 2023 (SSE-S3). You can choose a stronger option per bucket or per object:

| Option | Who manages the key | How it is used | When to choose |
|---|---|---|---|
| **SSE-S3** (`AES256`) | AWS, fully transparent | Default. AES-256, keys rotated by AWS, no extra cost, nothing to configure. | General data where you do not need key-level audit or control. |
| **SSE-KMS** (`aws:kms`) | AWS KMS key - AWS managed (`aws/s3`) or customer managed (CMK) | Each object encrypted with a data key protected by the KMS key. Every use is logged in CloudTrail; access to the key is itself an IAM/KMS permission. **S3 Bucket Keys** reduce KMS request cost by ~99 %. | Regulated data, separation of duties ("can read the bucket but not the key"), cross-account control. Recommended for Terraform state. |
| **DSSE-KMS** | KMS | Two independent layers of encryption with KMS keys. | Workloads that require dual-layer encryption (some government/compliance standards). |
| **SSE-C** | **You** supply the key in every request header | S3 encrypts/decrypts with your key and then discards it; it stores only a hash. Must use HTTPS. | You must own key material completely but still want S3 to do the crypto work. Rare. |
| **Client-side encryption** | You (AWS Encryption SDK, S3 Encryption Client, or your own code) | Data is encrypted *before* it leaves your machine; S3 only ever sees ciphertext. | Zero-trust requirements, end-to-end encryption, multi-cloud. |

**In transit** - all S3 endpoints support TLS. To make it mandatory add a bucket policy statement that denies requests where `aws:SecureTransport` is `false` (shown below).

Terraform sets default encryption with `aws_s3_bucket_server_side_encryption_configuration`.

## Bucket policies and Block Public Access

A **bucket policy** is a resource-based IAM policy attached to the bucket (max 20 KB). Because it contains a `Principal`, it can grant access to other accounts, to AWS services (CloudFront, CloudTrail, ALB logging) or - if you really want - to everyone (`"Principal": "*"`).

Example policy that (1) forces HTTPS, (2) lets a CI role read/write Terraform state, and (3) lets CloudFront serve a static site from the bucket through Origin Access Control:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyInsecureTransport",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:*",
      "Resource": [
        "arn:aws:s3:::vivek-devops-site",
        "arn:aws:s3:::vivek-devops-site/*"
      ],
      "Condition": { "Bool": { "aws:SecureTransport": "false" } }
    },
    {
      "Sid": "AllowCIRoleStateAccess",
      "Effect": "Allow",
      "Principal": { "AWS": "arn:aws:iam::123456789012:role/GitHubActionsTerraform" },
      "Action": ["s3:GetObject", "s3:PutObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::vivek-devops-site",
        "arn:aws:s3:::vivek-devops-site/*"
      ]
    },
    {
      "Sid": "AllowCloudFrontOAC",
      "Effect": "Allow",
      "Principal": { "Service": "cloudfront.amazonaws.com" },
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::vivek-devops-site/*",
      "Condition": {
        "StringEquals": {
          "AWS:SourceArn": "arn:aws:cloudfront::123456789012:distribution/E1ABCDEFGHIJKL"
        }
      }
    }
  ]
}
```

**Block Public Access (BPA)** is a bucket- and account-level safety switch with four settings. Since April 2023 **all four are ON by default** for every new bucket, and ACLs are disabled (`Object Ownership = Bucket owner enforced`):

| Setting | Effect |
|---|---|
| `BlockPublicAcls` | Reject new public ACLs on bucket or objects |
| `IgnorePublicAcls` | Ignore any existing public ACLs |
| `BlockPublicPolicy` | Reject a bucket policy that would grant public access |
| `RestrictPublicBuckets` | Even if a public policy exists, only the bucket owner and AWS services may use it |

With BPA on, a bucket cannot be made public by accident. The only legitimate reason to switch it off is classic S3 static website hosting; the better pattern in 2026 is to keep the bucket private and serve it through CloudFront with OAC, as in the policy above.

Terraform resources: `aws_s3_bucket_policy` and `aws_s3_bucket_public_access_block`.

## Common use cases

| Use case | How S3 is used | Related features |
|---|---|---|
| **Static website hosting** | HTML/CSS/JS uploaded to a bucket; served directly via the website endpoint (`http://<bucket>.s3-website.<region>.amazonaws.com`) or, preferably, through CloudFront for HTTPS, caching and a custom domain | Website configuration (`index.html`, `error.html`), CloudFront OAC, Route 53 |
| **Backups and disaster recovery** | EBS snapshots, RDS exports, database dumps, on-prem backups via AWS Backup / Storage Gateway | Versioning, Object Lock (WORM), Cross-Region Replication, Glacier classes |
| **Data lake** | Raw and curated data in Parquet/CSV, queried in place by Athena, Redshift Spectrum, EMR, Glue | Prefix layout (`year=/month=/day=`), S3 Select, Lake Formation |
| **Terraform remote state** | `terraform.tfstate` stored in a versioned, encrypted, private bucket with S3-native locking | Versioning, SSE-KMS, BPA, `use_lockfile = true` (Terraform 1.10+, replaces the DynamoDB lock table) |
| **Log storage** | CloudTrail, VPC Flow Logs, ALB/CloudFront access logs, application logs | Lifecycle rules to IA/Glacier, Athena for querying, bucket policy granting the logging service `s3:PutObject` |
| **Artifact / media storage** | CI build artifacts, Docker layer cache, user uploads, video assets | Pre-signed URLs for temporary upload/download, event notifications to Lambda/SQS, Transfer Acceleration |

Terraform backend block used in this session:

```hcl
terraform {
  backend "s3" {
    bucket       = "vivek-devops-tfstate-ap-south-1"
    key          = "session-18/terraform.tfstate"
    region       = "ap-south-1"
    encrypt      = true
    use_lockfile = true   # S3-native state locking (Terraform >= 1.10)
  }
}
```

## Useful AWS CLI commands

```bash
# Create (make bucket) and remove a bucket
aws s3 mb s3://vivek-devops-demo-bucket --region ap-south-1
aws s3 rb s3://vivek-devops-demo-bucket            # must be empty
aws s3 rb s3://vivek-devops-demo-bucket --force    # deletes all objects first

# List buckets, then objects (recursively, human readable sizes, with totals)
aws s3 ls
aws s3 ls s3://vivek-devops-demo-bucket/logs/ --recursive --human-readable --summarize

# Copy a single file up / down, choosing a storage class
aws s3 cp ./index.html s3://vivek-devops-demo-bucket/index.html
aws s3 cp ./backup.tar.gz s3://vivek-devops-demo-bucket/backups/ --storage-class STANDARD_IA
aws s3 cp s3://vivek-devops-demo-bucket/index.html ./downloaded.html

# Sync a local folder to the bucket (only changed files; --delete removes files that no longer exist locally)
aws s3 sync ./site/ s3://vivek-devops-demo-bucket/ --delete

# Move and delete objects
aws s3 mv s3://vivek-devops-demo-bucket/old.log s3://vivek-devops-demo-bucket/archive/old.log
aws s3 rm s3://vivek-devops-demo-bucket/logs/ --recursive

# Lower-level s3api calls for bucket settings
aws s3api put-bucket-encryption --bucket vivek-devops-demo-bucket \
    --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"aws:kms"}}]}'
aws s3api put-public-access-block --bucket vivek-devops-demo-bucket \
    --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws s3api get-bucket-policy --bucket vivek-devops-demo-bucket

# Generate a temporary download link (valid 1 hour)
aws s3 presign s3://vivek-devops-demo-bucket/report.pdf --expires-in 3600
```

## References

S3 User Guide: https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html | Storage classes: https://aws.amazon.com/s3/storage-classes/ | Bucket naming rules: https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucketnamingrules.html | Lifecycle management: https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html | Encryption: https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingEncryption.html | Terraform S3 backend: https://developer.hashicorp.com/terraform/language/backend/s3
