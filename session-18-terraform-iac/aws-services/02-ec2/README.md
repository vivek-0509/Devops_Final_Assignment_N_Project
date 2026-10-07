# AWS EC2 - Elastic Compute Cloud (Compute)

**Course:** DevOps - Session 18 (Terraform & Infrastructure as Code)
**Task 2:** AWS Services Research
**Author:** Vivek Singh Solanki (Roll No: 24bcs10338)

---

## What is EC2?

Amazon Elastic Compute Cloud (EC2) provides **resizable virtual machines** (called *instances*) in the AWS cloud. Instead of buying a server, you choose an image, a size, a network location and storage, and the instance is running within a minute. You pay per second (Linux) for as long as it runs, and you can stop, resize or terminate it at any time.

Things I found important to understand about EC2:

- An instance is **regional and zonal**: it lives in one Availability Zone inside one VPC subnet.
- Compute, storage and networking are **separate building blocks**: AMI (what to boot), instance type (how much CPU/RAM), EBS (disks), security group (firewall), key pair (SSH access), IAM instance profile (AWS permissions).
- Pricing models: **On-Demand** (pay as you go), **Savings Plans / Reserved Instances** (1 or 3 year commitment, up to ~72 % cheaper), **Spot** (spare capacity, up to 90 % cheaper, can be interrupted with a 2-minute warning), **Dedicated Hosts** (physical server for licensing/compliance).
- The **free tier** gives 750 hours/month of `t2.micro` / `t3.micro` (or `t4g.small` in some regions) for 12 months, which is what this course uses.
- Terraform manages EC2 with the `aws_instance` resource (and `aws_launch_template` + `aws_autoscaling_group` for fleets).

## AMI - Amazon Machine Image

An **AMI** is the template an instance boots from. It contains:

- A root volume snapshot (operating system, installed packages, your application if it is a custom image).
- **Launch permissions** - who may use it (private, specific accounts, or public).
- A **block device mapping** - which volumes to attach at launch.

| AMI source | Example | Notes |
|---|---|---|
| AWS provided | Amazon Linux 2023, Ubuntu 24.04, Windows Server 2025 | Patched regularly, free (except Windows/RHEL/SUSE licence cost in the hourly price) |
| AWS Marketplace | Hardened CIS images, vendor appliances | Extra software charge on top of EC2 price |
| Community | Images shared publicly by other accounts | Use with caution |
| Custom (your own) | "Golden image" built with Packer, created from a running instance | Fast boot with everything pre-installed; typical for Auto Scaling groups |

AMIs are **region-specific** - the same Amazon Linux image has a different `ami-...` ID in `ap-south-1` and `us-east-1`. A custom AMI can be copied to another region. The IDs also change every time AWS publishes a patched image, so hard-coding an AMI ID in Terraform goes stale; the usual pattern is a `data "aws_ami"` lookup or the public SSM parameter (`/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64`).

Virtually all modern AMIs are **EBS-backed** (root volume is an EBS volume, instance can be stopped) rather than instance-store-backed.

## Instance types

The instance type sets the vCPU count, memory, network bandwidth and (sometimes) GPU or local NVMe storage. The name encodes everything:

```
   m7g.xlarge
   | | |   |
   | | |   +-- size      : nano, micro, small, medium, large, xlarge, 2xlarge ... 48xlarge, metal
   | | +------ attribute : g = Graviton (ARM), a = AMD, i = Intel, n = enhanced networking, d = local NVMe disk
   | +-------- generation: 7 (newer = better price/performance)
   +---------- family    : m = general purpose
```

Main families covered in the course:

| Family | Category | Ratio (vCPU : GiB) | Examples | When to use |
|---|---|---|---|---|
| **t** | Burstable general purpose | 1 : 1 to 1 : 4 | `t3.micro` (2 vCPU, 1 GiB), `t3a.small`, `t4g.medium` | Dev/test, small web servers, low-traffic apps. CPU runs on *credits*: a baseline % of CPU is included and the instance bursts above it while credits last. `unlimited` mode lets it keep bursting for a fee. |
| **m** | General purpose (fixed performance) | 1 : 4 | `m5.large`, `m6i.xlarge`, `m7g.large` (Graviton) | Application servers, small/medium databases, anything "balanced". Default choice for production workloads. |
| **c** | Compute optimised | 1 : 2 | `c6g.xlarge`, `c7i.2xlarge`, `c7g.large` | CPU-heavy work: batch processing, video encoding, high-traffic web/API tiers, CI build runners, gaming servers. |
| **r** | Memory optimised | 1 : 8 | `r6i.xlarge`, `r7g.2xlarge` | In-memory caches (Redis), large relational/NoSQL databases, real-time analytics. (`x` and `u` families go even higher on RAM.) |
| **g** | GPU / accelerated | varies | `g4dn.xlarge` (NVIDIA T4), `g5.xlarge` (A10G), `g6.xlarge` (L4) | ML inference, graphics rendering, video transcoding, remote workstations. (`p` family is for large-scale ML *training*.) |

Other families worth knowing: `i` / `d` (storage optimised, local NVMe for Kafka, Elasticsearch), `hpc` (high performance computing), `mac` (macOS builds).

Rules of thumb:

- Start with `t3.micro` / `t3.small` for learning; move to `m` when you need predictable CPU.
- **Graviton (`g` suffix)** instances are usually 20-40 % cheaper per unit of performance; use them when the software supports ARM64 (most Linux workloads do).
- You can change the instance type of a stopped EBS-backed instance (vertical scaling), but for real scalability use an Auto Scaling group (horizontal scaling).

## Key pairs

A key pair is the SSH credential for Linux instances (for Windows it decrypts the Administrator password).

- AWS stores only the **public key**; the private key (`.pem`) is downloaded **once** at creation time and cannot be recovered. Lose it and you cannot SSH in with it.
- Algorithms: **ED25519** (recommended, smaller/faster) or **RSA 2048**.
- At launch, cloud-init writes the public key into `~/.ssh/authorized_keys` of the default user (`ec2-user` on Amazon Linux, `ubuntu` on Ubuntu).
- The file must be protected: `chmod 400 my-key.pem`, otherwise `ssh` refuses to use it.
- Alternatives that avoid opening port 22 at all: **EC2 Instance Connect** (short-lived key pushed via the API) and **SSM Session Manager** (browser/CLI shell through the SSM agent; needs the `AmazonSSMManagedInstanceCore` role, no inbound rule required).

```bash
aws ec2 create-key-pair --key-name vivek-devops-key --key-type ed25519 \
    --query 'KeyMaterial' --output text > vivek-devops-key.pem
chmod 400 vivek-devops-key.pem
ssh -i vivek-devops-key.pem ec2-user@<public-ip>
```

Terraform can also upload an existing public key with `aws_key_pair`, which is cleaner than creating keys by hand.

## Security Groups

A **security group (SG)** is a virtual firewall attached to the instance's network interface (ENI).

- **Stateful**: if an inbound request is allowed, the response is automatically allowed out (and vice versa). No need to add return-traffic rules.
- Contains **allow rules only**; there is no deny rule. Anything not explicitly allowed is dropped.
- Default behaviour of a new SG: **all inbound denied**, **all outbound allowed**.
- Rules can reference CIDR blocks, prefix lists, or **another security group** (e.g. "allow 3306 from `app-sg`"), which is the clean way to wire tiers together.
- Up to 5 SGs per ENI; all rules across them are evaluated together.
- Changes take effect immediately on all instances that use the SG.

Example `web-sg` for a public web server:

| Direction | Type | Protocol | Port | Source / Destination | Purpose |
|---|---|---|---|---|---|
| Inbound | HTTP | TCP | 80 | `0.0.0.0/0` | Public website traffic |
| Inbound | HTTPS | TCP | 443 | `0.0.0.0/0` | Public TLS traffic |
| Inbound | SSH | TCP | 22 | `203.0.113.25/32` (my IP) | Admin access only from my machine |
| Outbound | All traffic | All | All | `0.0.0.0/0` | Package updates, calls to AWS APIs |

Example `db-sg` for the database tier (no public access at all):

| Direction | Type | Protocol | Port | Source | Purpose |
|---|---|---|---|---|---|
| Inbound | MySQL | TCP | 3306 | `sg-0a1b2c3d (web-sg)` | Only web servers can reach the DB |
| Outbound | All traffic | All | All | `0.0.0.0/0` | Default |

## EBS - Elastic Block Store

EBS provides **persistent block storage** (virtual disks) for EC2. A volume lives in one AZ, is attached to one instance at a time (except `io2` Multi-Attach), and survives instance stop/start. The root volume is deleted on termination by default (`delete_on_termination = true`); extra volumes are kept.

| Volume type | Media | Baseline / max performance | Size range | Bootable | Typical use |
|---|---|---|---|---|---|
| **gp3** | SSD | 3,000 IOPS and 125 MB/s included; IOPS and throughput can be provisioned independently of size (16,000 IOPS / 1,000 MB/s standard, higher tiers on the latest generation) | 1 GiB - 16 TiB | Yes | **Default choice** for boot volumes, app servers, small/medium DBs. ~20 % cheaper than gp2. |
| gp2 | SSD | 3 IOPS per GiB, bursts to 3,000 | 1 GiB - 16 TiB | Yes | Previous generation; migrate to gp3. |
| **io2** (Block Express) | SSD | Provisioned, up to 256,000 IOPS and 4,000 MB/s, 99.999 % durability | 4 GiB - 64 TiB | Yes | Mission-critical, latency-sensitive databases (Oracle, SAP HANA, large PostgreSQL). |
| io1 | SSD | Provisioned, up to 64,000 IOPS | 4 GiB - 16 TiB | Yes | Older provisioned-IOPS tier. |
| **st1** | HDD | Throughput-based, 40 MB/s per TiB baseline, max 500 MB/s | 125 GiB - 16 TiB | No | Big sequential workloads: log processing, Kafka, data warehouses, ETL. |
| **sc1** | HDD | 12 MB/s per TiB baseline, max 250 MB/s | 125 GiB - 16 TiB | No | Cold, infrequently accessed data where cost matters most. |

Other EBS facts:

- Volumes can be **resized and re-typed while in use** (Elastic Volumes); you then grow the filesystem inside the OS.
- **Encryption** uses KMS and is transparent to the instance; enable "EBS encryption by default" per region so every new volume is encrypted.
- **Snapshots** are point-in-time, **incremental** backups stored internally in S3 (only changed blocks are saved after the first one). They can be copied across regions/accounts, turned into AMIs, restored to a new volume in any AZ, and automated with **Data Lifecycle Manager** or AWS Backup. Deleted snapshots can be protected with Recycle Bin.
- Instance store (local NVMe on `d`/`i` families) is faster but **ephemeral** - data is lost on stop/terminate.

## Public vs private IP (and Elastic IP)

| Address | Where it comes from | Behaviour | Cost |
|---|---|---|---|
| **Private IPv4** | The subnet's CIDR (e.g. `10.0.1.25`) | Assigned at launch, **stays the same** for the life of the instance, used for all traffic inside the VPC | Free |
| **Public IPv4** | Amazon's pool, if the subnet has *auto-assign public IP* enabled | Reachable from the internet (through the IGW). **Released on stop and a new one is assigned on start** - not stable | $0.005/hour for every public IPv4 (since Feb 2024) |
| **Elastic IP (EIP)** | Allocated to your account, then associated with an instance/ENI | **Static** - survives stop/start and can be moved to another instance (failover). Default quota 5 per region | Same $0.005/hour, whether attached or idle |
| **IPv6** | Globally unique address from the VPC's /56 block | Public by design (no NAT), stable | Free |

The instance itself only ever sees its private IP; the Internet Gateway performs the 1:1 NAT to the public/Elastic IP. For anything that needs a stable public endpoint, use an EIP or (better) put the instance behind a load balancer and point DNS at that.

## Instance lifecycle

```
   launch                                   stop / hibernate
  --------> [ pending ] ---> [ running ] ----------------------> [ stopping ] ---> [ stopped ]
                                ^  |                                                  |    |
                                |  | terminate                            start       |    | terminate
                                |  v                                                  |    v
                                | [ shutting-down ] ---> [ terminated ]               |  [ shutting-down ]
                                |                                                     |         |
                                +-----------------------------------------------------+         v
                                                                                        [ terminated ]

   reboot: instance stays "running" (same host, same IPs, like pressing reset)
```

| State | Billed? | What is happening |
|---|---|---|
| `pending` | No | AWS is allocating hardware, copying the AMI, running cloud-init |
| `running` | Yes (compute + EBS) | Normal operation |
| `stopping` | No (except hibernate prep) | OS shutting down |
| `stopped` | EBS only | Instance exists but no compute. You can change instance type, attach volumes, create AMIs. Public IPv4 is released; private IP and EBS data are kept |
| `shutting-down` | No | Terminate in progress |
| `terminated` | No | Instance is gone; root volume deleted by default; remains visible in the console for about an hour |

Hibernate saves RAM to the root EBS volume so the instance resumes exactly where it left off. Termination protection (`disable_api_termination`) prevents accidental `terminate` calls - worth enabling for anything stateful.

## Common use cases

- **Web and application servers** - behind an Application Load Balancer, in an Auto Scaling group across AZs.
- **Self-managed databases and caches** when a managed service does not fit (licensing, custom extensions).
- **CI/CD build agents** - GitHub Actions self-hosted runners, Jenkins agents, often on Spot instances.
- **Bastion / jump hosts** for reaching private subnets (increasingly replaced by SSM Session Manager).
- **Batch, data processing and ML** - compute-optimised or GPU instances started on demand.
- **Container hosts** - ECS/EKS worker nodes are plain EC2 instances underneath.
- **Learning Terraform** - `aws_instance` is the first real resource most people create, which is exactly what Session 18 does.

## Terraform example - `aws_instance`

```hcl
# Look up the latest Amazon Linux 2023 AMI instead of hard-coding an ID
data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-2023*-x86_64"]
  }
}

resource "aws_security_group" "web" {
  name        = "session18-web-sg"
  description = "Allow HTTP from anywhere and SSH from my IP"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.my_ip_cidr]   # e.g. "203.0.113.25/32"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "web" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = "t3.micro"
  subnet_id              = var.public_subnet_id
  vpc_security_group_ids = [aws_security_group.web.id]
  key_name               = "vivek-devops-key"
  iam_instance_profile   = var.instance_profile_name   # role instead of access keys

  root_block_device {
    volume_type = "gp3"
    volume_size = 20
    encrypted   = true
  }

  user_data = <<-EOF
    #!/bin/bash
    dnf install -y nginx
    echo "<h1>Session 18 - Terraform on EC2</h1>" > /usr/share/nginx/html/index.html
    systemctl enable --now nginx
  EOF

  tags = {
    Name        = "session18-web"
    Environment = "dev"
    ManagedBy   = "terraform"
  }
}

output "public_ip" {
  value = aws_instance.web.public_ip
}
```

## Useful AWS CLI commands

```bash
# Find the latest Amazon Linux 2023 AMI ID for the current region
aws ssm get-parameter --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 \
    --query 'Parameter.Value' --output text

# Launch an instance
aws ec2 run-instances --image-id ami-0123456789abcdef0 --instance-type t3.micro \
    --key-name vivek-devops-key --security-group-ids sg-0a1b2c3d --subnet-id subnet-0abc1234 \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=session18-web}]'

# List instances with name, state and public IP in a readable table
aws ec2 describe-instances \
    --query 'Reservations[].Instances[].{Name:Tags[?Key==`Name`]|[0].Value,ID:InstanceId,State:State.Name,IP:PublicIpAddress}' \
    --output table

# Lifecycle operations
aws ec2 stop-instances      --instance-ids i-0123456789abcdef0
aws ec2 start-instances     --instance-ids i-0123456789abcdef0
aws ec2 reboot-instances    --instance-ids i-0123456789abcdef0
aws ec2 terminate-instances --instance-ids i-0123456789abcdef0

# Elastic IP: allocate and attach
aws ec2 allocate-address --domain vpc
aws ec2 associate-address --instance-id i-0123456789abcdef0 --allocation-id eipalloc-0abc1234

# EBS snapshot of a volume
aws ec2 create-snapshot --volume-id vol-0abc1234 --description "pre-upgrade backup"
```

## References

EC2 User Guide: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/concepts.html | Instance types: https://aws.amazon.com/ec2/instance-types/ | EBS volume types: https://docs.aws.amazon.com/ebs/latest/userguide/ebs-volume-types.html | Instance lifecycle: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-lifecycle.html | Terraform `aws_instance`: https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/instance
