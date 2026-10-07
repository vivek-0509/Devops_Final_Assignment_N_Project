# AWS IAM - Identity and Access Management (Governance)

**Course:** DevOps - Session 18 (Terraform & Infrastructure as Code)
**Task 2:** AWS Services Research
**Author:** Vivek Singh Solanki (Roll No: 24bcs10338)

---

## What is IAM?

AWS Identity and Access Management (IAM) is the service that decides **who** can do **what** on **which** AWS resource. Every single API call that reaches AWS - whether it comes from the Console, the AWS CLI, an SDK, or Terraform - is authenticated and authorized by IAM before it runs. If IAM says no, nothing happens.

Key facts I noted while researching:

- IAM is a **global** service. Users, groups, roles and policies are not tied to a region.
- IAM itself is **free**. You only pay for the resources that identities actually use.
- Every account starts with one **root user** that has unrestricted access to everything. It should only be used for a handful of account-level tasks (billing setup, closing the account, changing support plan).
- IAM has four core building blocks: **Users, Groups, Roles and Policies**.
- For human sign-in across many accounts AWS now recommends **IAM Identity Center** (the successor of AWS SSO). It sits on top of IAM, but the permission model underneath is still IAM policies, so understanding IAM is still the foundation.
- IAM is also the backbone of Terraform workflows: the credentials Terraform uses are an IAM user's access keys or (better) an IAM role that the CI runner assumes.

## Users

An IAM **user** is an identity that represents a single person or application that interacts with AWS.

| Property | Details |
|---|---|
| Credentials | Console password and/or up to **2 access keys** (Access Key ID + Secret Access Key) |
| Scope | Belongs to exactly one AWS account |
| Default permissions | **None** - a brand new user cannot do anything until a policy is attached |
| Limits | 5,000 users per account (soft limit), 10 groups per user |
| MFA | Virtual (authenticator app), FIDO2 security key, or hardware TOTP token |
| Identifier | ARN, e.g. `arn:aws:iam::123456789012:user/vivek` |

Users have **long-term credentials**. That is exactly why AWS keeps pushing people away from them: a leaked access key works until someone rotates or deletes it. In 2026 the guidance is clear - humans should sign in through Identity Center (federation), applications should use roles, and plain IAM users with access keys should be the exception (for example an external SaaS tool that cannot assume a role).

## Groups

A **group** is simply a collection of users. Policies attached to the group apply to every user inside it, which makes permission management far easier than attaching policies to each user one by one.

- A user can be in up to **10 groups**; a group can hold any number of users.
- Groups **cannot be nested** (no group inside a group).
- A group is **not an identity** - you cannot reference a group as a `Principal` in a policy, and you cannot log in as a group.
- Typical groups: `Admins`, `Developers`, `ReadOnly`, `Billing`, `CI-Deploy`.

When a developer joins the team you add them to `Developers`; when they leave you remove them. Nothing else has to change.

## Roles

A **role** is an identity with permissions, but **without long-term credentials**. Something *assumes* the role and receives **temporary security credentials** (access key, secret key, session token) from AWS STS that expire after a configurable time (default 1 hour, maximum 12 hours).

Every role has two policies:

1. **Trust policy** - *who* is allowed to assume the role (an AWS service, another account, a federated identity, a specific user).
2. **Permissions policy** - *what* the role can do once assumed.

Common "who assumes it" scenarios:

| Scenario | Trusted principal |
|---|---|
| EC2 instance needs to read S3 | `ec2.amazonaws.com` (attached through an **instance profile**) |
| Lambda function writes to DynamoDB | `lambda.amazonaws.com` |
| Cross-account access (prod account trusts dev account) | `arn:aws:iam::111122223333:root` |
| GitHub Actions deploying with Terraform | OIDC provider `token.actions.githubusercontent.com` |
| Employee logging in via Identity Center | SAML / Identity Center permission set |

A sample trust policy that lets EC2 assume a role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "ec2.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

## Policies

A **policy** is a JSON document that defines permissions. Policies are *attached* to identities (users, groups, roles) or to resources (S3 bucket, SQS queue, KMS key).

Policy types:

| Type | Attached to | Notes |
|---|---|---|
| **Identity-based** | User / Group / Role | The most common type. Can be *AWS managed* (`AmazonS3ReadOnlyAccess`), *customer managed* (reusable, versioned) or *inline* (embedded in one identity). |
| **Resource-based** | Resource (S3, KMS, SQS, Lambda ...) | Contains a `Principal` element. Enables cross-account access without a role. |
| **Permissions boundary** | User / Role | Sets the *maximum* permissions an identity can have; does not grant anything by itself. |
| **Service Control Policy (SCP)** | Organization / OU / Account | Guardrail from AWS Organizations. Also only limits, never grants. |
| **Session policy** | Passed during `AssumeRole` | Further restricts a temporary session. |

Anatomy of a statement: `Sid` (optional label), `Effect` (`Allow` or `Deny`), `Action` (API operations), `Resource` (ARNs), `Condition` (optional extra checks), and `Principal` (only in resource-based policies).

Sample customer-managed policy - read/write to one application bucket, read-only listing of all buckets, and an explicit deny on deleting the bucket itself:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ListAllBuckets",
      "Effect": "Allow",
      "Action": ["s3:ListAllMyBuckets", "s3:GetBucketLocation"],
      "Resource": "*"
    },
    {
      "Sid": "AppBucketReadWrite",
      "Effect": "Allow",
      "Action": ["s3:ListBucket", "s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
      "Resource": [
        "arn:aws:s3:::vivek-devops-app-data",
        "arn:aws:s3:::vivek-devops-app-data/*"
      ],
      "Condition": {
        "Bool": { "aws:SecureTransport": "true" }
      }
    },
    {
      "Sid": "NeverDeleteTheBucket",
      "Effect": "Deny",
      "Action": "s3:DeleteBucket",
      "Resource": "arn:aws:s3:::vivek-devops-app-data"
    }
  ]
}
```

Useful things to remember about the JSON:

- `"Version": "2012-10-17"` is the current policy language version and should always be present (it enables policy variables such as `${aws:username}`).
- Actions support wildcards: `s3:Get*`, `ec2:Describe*`. `"Action": "*"` with `"Resource": "*"` is full admin.
- Managed policies are limited to 6,144 characters; a user can have at most 10 managed policies attached by default.

## Permissions - how evaluation works

When a request comes in, IAM gathers *every* policy that applies to the caller (identity policies, group policies, resource policies, boundaries, SCPs, session policies) and evaluates them together. The outcome follows a fixed order:

```
  1. Start with  IMPLICIT DENY   (nothing is allowed by default)
  2. Is there an EXPLICIT DENY   in any applicable policy?   --> request DENIED, stop.
  3. Is there an EXPLICIT ALLOW  in an applicable policy?    --> request ALLOWED
        (and the SCP, permissions boundary and session policy must ALSO allow it)
  4. Otherwise                                                --> IMPLICIT DENY
```

In short: **Explicit Deny > Explicit Allow > Implicit Deny.**

Practical consequences:

- A `Deny` statement anywhere beats an `Allow` everywhere else. That is why `Deny` is used for guardrails ("nobody may disable CloudTrail").
- Attaching `AdministratorAccess` to a user does not help if an SCP on the account denies the action.
- Resource-based policies can grant access to a principal in the *same* account on their own. For a *different* account, both the resource policy and the caller's identity policy must allow the action.
- A permissions boundary never grants; the effective permission is the **intersection** of the boundary and the identity policy.

## Least privilege

Least privilege means granting **only the permissions required to perform a task, and nothing more** - for the shortest time necessary.

How I would apply it in practice:

1. Start from what the workload *actually* calls (CloudTrail logs and IAM Access Analyzer's "generate policy" feature show real API usage).
2. Scope `Resource` to specific ARNs instead of `*`.
3. Add `Condition` keys: restrict by source IP (`aws:SourceIp`), by region (`aws:RequestedRegion`), by tag (`aws:ResourceTag/Environment`), or require MFA (`aws:MultiFactorAuthPresent`).
4. Prefer roles with short sessions over users with permanent keys.
5. Review and remove unused permissions regularly. IAM shows "last accessed" information per service.
6. Use **permissions boundaries** when delegating the ability to create roles (e.g. a developer may create Lambda roles, but those roles can never exceed the boundary).

A policy that says `"Action": "s3:*", "Resource": "*"` for a service that only needs to read one bucket is the classic violation. It works, but a single compromised credential then exposes every bucket in the account.

## IAM best practices

These are the recommendations from the official IAM user guide, summarised in my own words:

| # | Practice | Why it matters |
|---|---|---|
| 1 | **Lock down the root user** - enable MFA, delete its access keys, use it only for the few tasks that require it | Root cannot be restricted by policies; a root compromise is a full account compromise. AWS now enforces MFA on root for management accounts. |
| 2 | **Enable MFA for every human identity** | Passwords leak; MFA blocks most credential-stuffing and phishing attacks. |
| 3 | **Use roles for workloads, not access keys** - EC2 instance profiles, Lambda execution roles, ECS task roles | Temporary credentials rotate automatically and never sit in a config file or git repo. |
| 4 | **Use federation / IAM Identity Center for people** | One corporate login, central off-boarding, no per-account users to manage. |
| 5 | **Rotate access keys** where long-term keys are unavoidable (every 90 days or less) and keep at most one active key per user | Limits the window during which a leaked key is useful. |
| 6 | **Apply least privilege and scope resources** | See section above. |
| 7 | **Use groups, not per-user policies** | Easier audit, consistent permissions, fewer mistakes. |
| 8 | **Prefer customer-managed policies over inline policies** | Reusable, versioned (up to 5 versions, roll back possible), visible in one place. |
| 9 | **Use conditions** (MFA, source IP, VPC endpoint, tags) | Adds a second dimension to "allowed or not". |
| 10 | **Turn on IAM Access Analyzer and CloudTrail** | Finds resources shared outside the account, flags unused roles/keys, validates policies before deployment. |
| 11 | **Set a strong password policy** (length, complexity, expiry) | Baseline hygiene for any remaining console users. |
| 12 | **Audit regularly** - credential report, last-accessed data, remove unused users/roles | Stale identities are the easiest way in. |
| 13 | **Never commit credentials** - use `aws configure`, environment variables, or SSO profiles; add `.env`/`*.tfvars` with secrets to `.gitignore` | Leaked keys on GitHub get exploited within minutes. |

## Common use cases

- **Team access management** - developers, operators and auditors in different groups with different managed policies.
- **EC2 / ECS / Lambda permissions** - an instance profile or execution role gives the workload access to S3, DynamoDB, Secrets Manager without any stored key.
- **CI/CD pipelines** - GitHub Actions or GitLab CI assumes a deployment role via OIDC and runs `terraform apply`; no secrets stored in the pipeline.
- **Cross-account access** - a central "shared services" account assumes roles in dev/stage/prod accounts.
- **Terraform remote state protection** - a policy that allows `s3:GetObject`/`PutObject` only on the state bucket and nothing else.
- **Break-glass access** - an emergency admin role that requires MFA and logs every assumption to CloudTrail.
- **Guardrails** - SCPs that deny leaving the approved regions or deleting CloudTrail trails, regardless of who asks.

## Diagram - Users, Groups, Policies and Role assumption

```
   USERS            GROUPS                       POLICIES
   -----            ------                       --------
  +--------+                                  +-----------------------------+
  | vivek  |---+                              | AmazonEC2ReadOnlyAccess     |
  +--------+   |    +--------------+          |   (AWS managed)             |
               +--->|  Developers  |--------->+-----------------------------+
  +--------+   |    +--------------+          | DevS3BucketAccess           |
  | priya  |---+                              |   (customer managed)        |
  +--------+                                  +-----------------------------+

  +--------+         +--------------+          +-----------------------------+
  | ci-bot |-------->|  CI-Deploy   |--------->| TerraformDeployPolicy       |
  +--------+         +--------------+          +-----------------------------+


   ROLE ASSUMPTION (temporary credentials from STS)

  +---------------+   sts:AssumeRole    +--------------------------+   temp creds    +--------------+
  | EC2 instance  | ------------------> | Role: AppServerRole      | --------------> |  S3 bucket   |
  | (instance     |   trust policy      |  Trust : ec2.amazonaws   |  (expire after  |  DynamoDB    |
  |  profile)     |   allows EC2        |  Perms : S3 + DynamoDB   |   1h - 12h)     |  table       |
  +---------------+                     +--------------------------+                 +--------------+

  Same pattern for: Lambda, ECS tasks, GitHub Actions (OIDC), users in another account.
```

## Useful AWS CLI commands

```bash
# Who am I? (account id, ARN of the user/role currently in use) - the first thing to run when debugging
aws sts get-caller-identity

# List users, groups and roles in the account
aws iam list-users
aws iam list-groups
aws iam list-roles --query 'Roles[].RoleName'

# Create a user and add it to a group
aws iam create-user --user-name vivek-dev
aws iam create-group --group-name Developers
aws iam add-user-to-group --user-name vivek-dev --group-name Developers

# Attach an AWS managed policy to the group (preferred) or directly to the user
aws iam attach-group-policy --group-name Developers \
    --policy-arn arn:aws:iam::aws:policy/AmazonEC2ReadOnlyAccess
aws iam attach-user-policy --user-name vivek-dev \
    --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess

# Create a customer managed policy from a JSON file and a role with a trust policy
aws iam create-policy --policy-name DevS3BucketAccess --policy-document file://policy.json
aws iam create-role --role-name AppServerRole --assume-role-policy-document file://trust.json
aws iam attach-role-policy --role-name AppServerRole \
    --policy-arn arn:aws:iam::123456789012:policy/DevS3BucketAccess

# See what is attached, and test a role
aws iam list-attached-user-policies --user-name vivek-dev
aws sts assume-role --role-arn arn:aws:iam::123456789012:role/AppServerRole \
    --role-session-name test-session

# Audit: credential report for every user (CSV, base64 encoded)
aws iam generate-credential-report && aws iam get-credential-report --query Content --output text | base64 -d
```

## References

AWS IAM User Guide: https://docs.aws.amazon.com/IAM/latest/UserGuide/introduction.html | Policy evaluation logic: https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_evaluation-logic.html | IAM best practices: https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html | IAM CLI reference: https://docs.aws.amazon.com/cli/latest/reference/iam/
