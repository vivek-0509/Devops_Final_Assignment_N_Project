# AWS VPC - Virtual Private Cloud (Networking)

**Course:** DevOps - Session 18 (Terraform & Infrastructure as Code)
**Task 2:** AWS Services Research
**Author:** Vivek Singh Solanki (Roll No: 24bcs10338)

---

## What is VPC?

Amazon Virtual Private Cloud (VPC) is a **logically isolated virtual network** inside an AWS region that I control. Everything that has a network interface in AWS - EC2 instances, RDS databases, load balancers, Lambda functions attached to a VPC, EKS nodes - lives inside a VPC. It is the AWS equivalent of the physical network in an on-premises data centre: I choose the IP address range, carve it into subnets, decide how traffic is routed, and put firewalls in front of resources.

Key points:

- A VPC is **regional** and spans all Availability Zones (AZs) in that region. Subnets are **zonal** - each one sits in exactly one AZ.
- Every account gets a **default VPC** per region (`172.31.0.0/16`) with public subnets so you can launch an instance quickly. For anything real you build a **custom VPC**.
- The main building blocks are: CIDR block, subnets, route tables, Internet Gateway (IGW), NAT Gateway, Security Groups and Network ACLs.
- Other features worth knowing: VPC peering, Transit Gateway, VPC endpoints (private access to S3/DynamoDB without going through the internet), VPC Flow Logs, and DNS settings (`enableDnsSupport`, `enableDnsHostnames`).
- VPC itself is free. You pay for NAT Gateways, data transfer, VPC endpoints, and some optional features.

For this course, VPC is the foundation layer that Terraform creates first; EC2, RDS and the rest are placed inside it.

## CIDR (Classless Inter-Domain Routing)

A CIDR block is written as `network/prefix`, e.g. `10.0.0.0/16`. The prefix says how many of the 32 bits of an IPv4 address are fixed (the network part); the remaining bits identify hosts.

Number of addresses = 2^(32 - prefix).

| CIDR | Fixed bits | Host bits | Total addresses | Typical use |
|------|-----------|-----------|-----------------|-------------|
| `10.0.0.0/16` | 16 | 16 | 2^16 = **65,536** | Whole VPC |
| `10.0.0.0/20` | 20 | 12 | 4,096 | Large subnet |
| `10.0.1.0/24` | 24 | 8 | 2^8 = **256** | Normal subnet |
| `10.0.1.0/28` | 28 | 4 | 16 | Smallest subnet AWS allows |

Worked example:

- VPC = `10.0.0.0/16` -> addresses `10.0.0.0` to `10.0.255.255` = 65,536 IPs.
- Subnet = `10.0.1.0/24` -> addresses `10.0.1.0` to `10.0.1.255` = 256 IPs.
- AWS **reserves 5 addresses in every subnet**, so a `/24` gives **256 - 5 = 251 usable** IPs:

| Address (for `10.0.1.0/24`) | Reserved for |
|-----------------------------|--------------|
| `10.0.1.0` | Network address |
| `10.0.1.1` | VPC router |
| `10.0.1.2` | Amazon-provided DNS (Route 53 Resolver) |
| `10.0.1.3` | Reserved for future use |
| `10.0.1.255` | Network broadcast address (broadcast is not supported in a VPC, but the address is still reserved) |

Rules and good practice:

- A VPC CIDR must be between `/16` (largest) and `/28` (smallest). Use RFC 1918 private ranges: `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`.
- Subnet CIDRs must sit inside the VPC CIDR and must not overlap each other.
- The primary CIDR cannot be changed after creation, but up to 4 secondary CIDR blocks can be added.
- Avoid overlapping ranges with other VPCs or on-prem networks you may need to peer with later. Giving each VPC a unique `/16` (`10.0.0.0/16`, `10.1.0.0/16`, ...) keeps peering simple.

## Subnets

A subnet is a range of IP addresses inside the VPC that lives in a **single Availability Zone**. Resources are launched into subnets, not directly into the VPC.

- Each subnet has exactly one route table and one Network ACL associated with it.
- A common pattern is one **public** and one **private** subnet per AZ, across at least two AZs for high availability.
- The `map_public_ip_on_launch` (auto-assign public IPv4) setting decides whether instances launched in the subnet automatically get a public IP.
- Subnet types in practice: public (web/load balancers/NAT), private (application servers), isolated/database (no internet route at all).

Example layout for `10.0.0.0/16`:

| Subnet | CIDR | AZ | Type |
|--------|------|----|------|
| public-1a | `10.0.1.0/24` | ap-south-1a | Public |
| public-1b | `10.0.2.0/24` | ap-south-1b | Public |
| private-1a | `10.0.101.0/24` | ap-south-1a | Private |
| private-1b | `10.0.102.0/24` | ap-south-1b | Private |

## Route tables

A route table contains a set of rules (routes) that decide where network traffic from a subnet is sent. Each route has a **destination** (CIDR) and a **target** (local, IGW, NAT GW, peering connection, endpoint, etc.).

- Every VPC has a **main route table**; subnets without an explicit association use it. Best practice is to leave the main table private and create custom tables.
- Every route table contains an unchangeable **local** route for the VPC CIDR so subnets can talk to each other.
- A subnet can be associated with only one route table, but one route table can serve many subnets.
- **Longest prefix match** wins: a `/24` route is more specific than `0.0.0.0/0`, so it takes priority.

| Destination | Target | Meaning |
|-------------|--------|---------|
| `10.0.0.0/16` | `local` | Traffic inside the VPC |
| `0.0.0.0/0` | `igw-xxxx` | Everything else goes to the internet (public RT) |
| `0.0.0.0/0` | `nat-xxxx` | Everything else goes out via NAT (private RT) |
| `172.16.0.0/16` | `pcx-xxxx` | Peered VPC |

## Internet Gateway

An Internet Gateway (IGW) is a horizontally scaled, redundant, highly available VPC component that allows communication between the VPC and the internet.

- One IGW can be attached to **one VPC**, and a VPC can have only **one IGW**.
- It performs one-to-one NAT between an instance's private IP and its public/Elastic IP, so the instance never actually sees its public address.
- Having an IGW attached does nothing on its own - a subnet's route table still needs a `0.0.0.0/0 -> igw` route, and the instance needs a public IP plus a Security Group that allows the traffic.
- IGW is free; you only pay for data transfer out.

## NAT Gateway

A NAT (Network Address Translation) Gateway lets instances in a **private subnet** initiate outbound connections to the internet (for OS updates, pulling Docker images, calling external APIs) while blocking unsolicited inbound connections from the internet.

- It is a managed service: AWS handles scaling (up to 100 Gbps) and availability within its AZ.
- It must be created in a **public subnet** and needs an **Elastic IP**. The private subnet's route table points `0.0.0.0/0` at the NAT Gateway.
- A NAT Gateway is **AZ-specific**. For high availability create one per AZ and give each private subnet a route to the NAT in its own AZ; otherwise an AZ failure takes down outbound internet for all private subnets.
- Pricing: per hour plus per GB processed, so it is often the most expensive piece of a small lab VPC. For labs, delete it when done or use a NAT instance / VPC endpoints for S3 and DynamoDB instead.
- A NAT Gateway does not need a Security Group; it is controlled by the NACL of its subnet and by the routing.

## Security Groups

A Security Group (SG) is a **virtual firewall at the instance (network interface) level**.

- Rules are **allow only**; anything not explicitly allowed is denied. There are no deny rules.
- **Stateful**: if an inbound request is allowed, the response is automatically allowed out, regardless of outbound rules (and vice versa).
- Default behaviour: deny all inbound, allow all outbound.
- Rules can reference CIDRs, prefix lists, or **other Security Groups** (e.g. "allow 3306 from the app-tier SG") - this is the cleanest way to wire tiers together.
- Several SGs can be attached to one network interface (default limit 5), and all their rules are combined.
- Changes take effect immediately.

Example web-tier SG:

| Direction | Protocol | Port | Source/Destination | Purpose |
|-----------|----------|------|--------------------|---------|
| Inbound | TCP | 80 | `0.0.0.0/0` | HTTP from anywhere |
| Inbound | TCP | 443 | `0.0.0.0/0` | HTTPS from anywhere |
| Inbound | TCP | 22 | `203.0.113.10/32` | SSH from my IP only |
| Outbound | All | All | `0.0.0.0/0` | Default allow all |

## Network ACLs

A Network ACL (NACL) is an optional **subnet-level** firewall. Every subnet must have one; the default NACL allows all traffic in and out, a newly created custom NACL denies everything until rules are added.

- Rules are **numbered** (1 to 32766) and evaluated **from the lowest number upward**; the first matching rule is applied and evaluation stops. The final `*` rule denies anything that did not match.
- Supports both **allow** and **deny** rules, so it is the right tool to block a specific malicious IP range.
- **Stateless**: return traffic must be explicitly allowed. If a web server accepts port 80 inbound, the outbound rules must allow the **ephemeral port range** (`1024-65535`) so responses can leave.
- One NACL can be associated with many subnets, but a subnet has only one NACL.

### Security Groups vs Network ACLs

| Aspect | Security Group | Network ACL |
|--------|----------------|-------------|
| Operates at | Instance / ENI level | Subnet level |
| State | **Stateful** - return traffic automatically allowed | **Stateless** - return traffic must be allowed explicitly (ephemeral ports) |
| Rule types | **Allow** rules only | **Allow and Deny** rules |
| Rule evaluation | All rules evaluated together; any match allows | Rules evaluated in **number order**, lowest first; first match wins |
| Default (custom) | Deny all inbound, allow all outbound | Custom NACL denies all; default NACL allows all |
| Applies to | Only instances the SG is attached to | Every resource in the associated subnets |
| Can reference other SGs | Yes | No, CIDR only |
| Typical use | Primary firewall for every workload | Extra, coarse layer: block known-bad IPs, isolate subnets |

Traffic entering an instance has to pass **both** layers: NACL of the subnet first, then the Security Group.

## Public vs private subnet

Nothing in the subnet object itself says "public" or "private". The difference is purely about routing and addressing:

A subnet is **public** when **both** are true:

1. Its route table has a route `0.0.0.0/0 -> Internet Gateway`.
2. Instances in it have a **public IPv4 address or Elastic IP** (via auto-assign on the subnet or assigned at launch).

A subnet is **private** when its route table has **no route to an IGW**. Instances only have private IPs. If they need outbound internet, the route table sends `0.0.0.0/0` to a **NAT Gateway** in a public subnet. Nobody on the internet can open a connection to them.

| | Public subnet | Private subnet |
|--|---------------|----------------|
| `0.0.0.0/0` route target | Internet Gateway | NAT Gateway (or none) |
| Public IP on instances | Yes | No |
| Inbound from internet | Possible (if SG allows) | Not possible |
| Outbound to internet | Direct via IGW | Via NAT Gateway |
| Typical workloads | Load balancers, bastion hosts, NAT Gateway | App servers, databases, caches, EKS worker nodes |

## Architecture diagram

```
                                   Internet
                                      |
                        +-------------+--------------+
                        |   Internet Gateway (IGW)   |
                        +-------------+--------------+
                                      |
 +------------------------------------+------------------------------------------+
 |  VPC  10.0.0.0/16                  |                                           |
 |                                    |                                           |
 |   +--------------------------------+-----+    +--------------------------------+ |
 |   | Public subnet  10.0.1.0/24 (1a)      |    | Private subnet 10.0.101.0/24 (1a)| |
 |   |                                      |    |                                | |
 |   |   +-------------+  +-------------+   |    |  +-------------+  +----------+ | |
 |   |   | Web / ALB   |  | NAT Gateway |<--------+--| App EC2     |  | RDS      | | |
 |   |   | public IP   |  | Elastic IP  |   |    |  | private IP  |  | private  | | |
 |   |   +-------------+  +-------------+   |    |  +-------------+  +----------+ | |
 |   |                                      |    |                                | |
 |   +-----------------+--------------------+    +---------------+----------------+ |
 |                     |                                         |                  |
 |          Public route table                        Private route table          |
 |          10.0.0.0/16 -> local                      10.0.0.0/16 -> local         |
 |          0.0.0.0/0   -> igw-xxxx                   0.0.0.0/0   -> nat-xxxx      |
 |                                                                                 |
 |   NACL: subnet boundary        Security Groups: around each instance / ENI      |
 +---------------------------------------------------------------------------------+
```

Flow: a user reaches the web tier through the IGW; the app server in the private subnet reaches the internet (e.g. `apt update`) through the NAT Gateway, which sits in the public subnet and exits through the IGW. RDS has no internet route at all.

## Terraform snippet

```hcl
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = "devops-vpc" }
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "ap-south-1a"
  map_public_ip_on_launch = true          # makes launched instances get a public IP

  tags = { Name = "devops-public-1a" }
}

resource "aws_subnet" "private" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.101.0/24"
  availability_zone = "ap-south-1a"

  tags = { Name = "devops-private-1a" }
}

resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.main.id

  tags = { Name = "devops-igw" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"               # this route is what makes the subnet public
    gateway_id = aws_internet_gateway.igw.id
  }

  tags = { Name = "devops-public-rt" }
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

# Optional: NAT for the private subnet
resource "aws_eip" "nat" {
  domain = "vpc"
}

resource "aws_nat_gateway" "nat" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public.id     # NAT GW always lives in a public subnet
  depends_on    = [aws_internet_gateway.igw]
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.nat.id
  }
}

resource "aws_route_table_association" "private" {
  subnet_id      = aws_subnet.private.id
  route_table_id = aws_route_table.private.id
}
```

## AWS CLI commands

```bash
# List all VPCs in the current region
aws ec2 describe-vpcs

# Compact view: ID, CIDR and whether it is the default VPC
aws ec2 describe-vpcs \
  --query "Vpcs[].{Id:VpcId,CIDR:CidrBlock,Default:IsDefault}" --output table

# Create a VPC with a Name tag
aws ec2 create-vpc --cidr-block 10.0.0.0/16 \
  --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=devops-vpc}]'

# List subnets of a specific VPC
aws ec2 describe-subnets --filters "Name=vpc-id,Values=vpc-0123456789abcdef0" \
  --query "Subnets[].{Id:SubnetId,CIDR:CidrBlock,AZ:AvailabilityZone,PublicIP:MapPublicIpOnLaunch}" \
  --output table

# Create a subnet inside the VPC
aws ec2 create-subnet --vpc-id vpc-0123456789abcdef0 \
  --cidr-block 10.0.1.0/24 --availability-zone ap-south-1a

# Create and attach an Internet Gateway
aws ec2 create-internet-gateway
aws ec2 attach-internet-gateway --internet-gateway-id igw-0abc12345 --vpc-id vpc-0123456789abcdef0

# Inspect route tables of the VPC
aws ec2 describe-route-tables --filters "Name=vpc-id,Values=vpc-0123456789abcdef0"

# Clean up (must detach IGW and delete subnets first)
aws ec2 delete-vpc --vpc-id vpc-0123456789abcdef0
```

## Summary

- VPC = my own isolated network in a region; subnets = AZ-level slices of its CIDR.
- Route tables decide where traffic goes; IGW gives inbound/outbound internet to public subnets; NAT Gateway gives outbound-only internet to private subnets.
- Security Groups (stateful, allow-only, instance level) are the main firewall; NACLs (stateless, allow+deny, subnet level) are a coarse second layer.
- A subnet is public only because of a `0.0.0.0/0 -> igw` route plus public IPs - not because of any flag on the subnet.

## References

AWS VPC User Guide: https://docs.aws.amazon.com/vpc/latest/userguide/what-is-amazon-vpc.html | Subnets and CIDR: https://docs.aws.amazon.com/vpc/latest/userguide/configure-subnets.html | Security Groups: https://docs.aws.amazon.com/vpc/latest/userguide/vpc-security-groups.html | Network ACLs: https://docs.aws.amazon.com/vpc/latest/userguide/vpc-network-acls.html | NAT Gateways: https://docs.aws.amazon.com/vpc/latest/userguide/vpc-nat-gateway.html | Terraform `aws_vpc`: https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/vpc
