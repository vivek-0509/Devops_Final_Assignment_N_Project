# AWS DynamoDB & RDS (Databases)

**Course:** DevOps - Session 18 (Terraform & Infrastructure as Code)
**Task 2:** AWS Services Research
**Author:** Vivek Singh Solanki (Roll No: 24bcs10338)

---

AWS offers many database services, but the two I will meet most often as a DevOps engineer are **DynamoDB** (NoSQL, serverless) and **RDS** (managed relational). They solve different problems, so this document covers each one and then compares them.

## Part 1 - Amazon DynamoDB

### What is DynamoDB?

DynamoDB is a fully managed **NoSQL key-value and document database**. There are no servers, no OS, no patching and no capacity to size up front (unless I choose provisioned mode). AWS promises **single-digit millisecond latency at any scale** - the same table can serve a few requests a day or millions per second.

- **Serverless**: I create a table and start writing; AWS spreads data across partitions and replicates it synchronously across **three Availability Zones** in the region.
- **Schema-less**: only the primary key is fixed; every item can have different attributes.
- Accessed through an HTTPS API (`PutItem`, `GetItem`, `Query`, `Scan`, `UpdateItem`, `DeleteItem`, `BatchWriteItem`), not SQL (PartiQL is available as a SQL-like syntax).
- Extras: **DynamoDB Streams** (change feed for Lambda), **TTL** (auto-expire items), **Global Tables** (multi-region active-active), **DAX** (in-memory cache), **transactions** (ACID across up to 100 items), **point-in-time recovery**, encryption at rest by default.
- Limits to remember: an item can be at most **400 KB**; a table can have 20 Global Secondary Indexes and 5 Local Secondary Indexes.

In this course DynamoDB appears as the **state-locking table for the Terraform S3 backend**: a tiny table with a `LockID` partition key stops two people running `terraform apply` on the same state at once.

### Tables, Items, Attributes

| DynamoDB term | Relational equivalent | Description |
|---------------|-----------------------|-------------|
| **Table** | Table | A collection of items. Must have a primary key; nothing else is fixed. |
| **Item** | Row | A single record, identified uniquely by its primary key. Max 400 KB. |
| **Attribute** | Column | A name/value pair inside an item. Items in the same table can have different attributes. |

Attribute data types: scalar (`S` string, `N` number, `B` binary, `BOOL`, `NULL`), document (`L` list, `M` map - nested JSON), and set (`SS`, `NS`, `BS`).

### Partition key

The **partition key** (also called the hash key) is the mandatory part of the primary key.

- DynamoDB runs the partition key value through a hash function and uses the result to decide **which physical partition** stores the item.
- When used alone (simple primary key), the partition key value must be **unique** per item.
- A good partition key has **many distinct values** that are accessed evenly (`CustomerID`, `DeviceID`, `OrderID`). A bad one has few values or one very hot value (`Status`, `Country`) and creates "hot partitions" that get throttled.

### Sort key

The optional **sort key** (range key) is the second half of a **composite primary key**.

- Items with the same partition key are stored **together, physically sorted** by the sort key.
- The combination of partition key + sort key must be unique, but the partition key alone can repeat.
- The sort key enables range queries: `begins_with`, `between`, `<`, `>`, and reading the newest N items by sorting descending.

### Example table design - Orders

| Setting | Value |
|---------|-------|
| Table name | `Orders` |
| Partition key | `CustomerID` (String) |
| Sort key | `OrderDate` (String, ISO 8601 so that string sort = chronological sort) |
| GSI | `OrderID-index` on `OrderID` so a single order can be found without knowing the customer |

Access patterns this design supports:

| Access pattern | Operation |
|----------------|-----------|
| All orders for one customer | `Query` where `CustomerID = :c` |
| Orders for a customer in October 2026 | `Query` where `CustomerID = :c AND begins_with(OrderDate, "2026-10")` |
| Most recent 10 orders for a customer | `Query` with `ScanIndexForward = false`, `Limit = 10` |
| One specific order (customer + date known) | `GetItem` with both keys |
| Find by `OrderID` only | `Query` on the `OrderID-index` GSI |

Sample item in DynamoDB JSON format (what the CLI and low-level API use):

```json
{
  "CustomerID":  { "S": "CUST-1001" },
  "OrderDate":   { "S": "2026-10-07T09:30:00Z" },
  "OrderID":     { "S": "ORD-78421" },
  "Status":      { "S": "SHIPPED" },
  "TotalAmount": { "N": "2499.00" },
  "Currency":    { "S": "INR" },
  "ShippingAddress": {
    "M": {
      "City":    { "S": "Ahmedabad" },
      "Pincode": { "S": "380015" }
    }
  },
  "Items": {
    "L": [
      { "M": { "SKU": { "S": "KB-101" }, "Qty": { "N": "1" }, "Price": { "N": "1999.00" } } },
      { "M": { "SKU": { "S": "MS-220" }, "Qty": { "N": "1" }, "Price": { "N": "500.00" } } }
    ]
  }
}
```

### Capacity modes

| | On-demand | Provisioned |
|--|-----------|-------------|
| How it works | Pay per request; DynamoDB scales instantly to any traffic | I set **RCUs** and **WCUs** per second (optionally with Auto Scaling) |
| Unit of billing | Read request units / write request units consumed | Capacity units reserved per hour, whether used or not |
| Best for | Unknown or spiky traffic, new apps, dev/test, Terraform lock tables | Steady, predictable traffic where reserved capacity is cheaper |
| Throttling | Only if traffic doubles faster than the previous peak in a short window | When consumed capacity exceeds provisioned capacity (unless Auto Scaling catches up) |
| Switching | Can switch between modes once every 24 hours | |

Capacity unit definitions: 1 **RCU** = one strongly consistent read per second of an item up to 4 KB (or two eventually consistent reads); 1 **WCU** = one write per second of an item up to 1 KB. A 3 KB item needs 1 RCU to read and 3 WCUs to write.

### DynamoDB use cases

- Session stores, shopping carts and user profiles for web/mobile apps.
- Serverless backends with Lambda and API Gateway.
- Gaming leaderboards and real-time counters.
- IoT and time-series data at high write rates (device ID as partition key, timestamp as sort key).
- Terraform state locking, feature flags, configuration lookup tables.

## Part 2 - Amazon RDS

### What is RDS?

Amazon Relational Database Service (RDS) is a **managed relational database** service. I still get a normal database engine with SQL, tables, joins, foreign keys and ACID transactions, but AWS takes care of the operational work: provisioning the server, installing the engine, OS and minor version patching, automated backups, monitoring, storage scaling and failover.

What I still own: the schema, indexes, query tuning, parameter groups, user accounts and the application code. I do **not** get SSH access to the underlying host.

### Supported engines

| Engine | Notes |
|--------|-------|
| **MySQL** | Most common open-source choice; community edition. |
| **PostgreSQL** | Feature-rich open source, popular for new applications. |
| **MariaDB** | MySQL fork, fully open source. |
| **Oracle** | Licence included or bring-your-own-licence (BYOL). |
| **Microsoft SQL Server** | Express, Web, Standard and Enterprise editions; licence included. |
| **Amazon Aurora** | AWS-built engine compatible with MySQL and PostgreSQL. Storage is distributed across 3 AZs (6 copies), scales automatically up to 128 TiB (256 TiB on newer versions), up to 5x MySQL / 3x PostgreSQL throughput, faster failover, and a Serverless v2 option. |
| IBM Db2 | Added in late 2023 for enterprise migrations. |

### DB instances

A **DB instance** is an isolated database environment running one engine. It is sized by an **instance class** and **storage**.

Instance class families:

| Family | Examples | Purpose |
|--------|----------|---------|
| Burstable | `db.t3.micro`, `db.t4g.micro` | Dev/test, small workloads; `db.t3.micro`/`db.t4g.micro` are in the free tier for 12 months |
| General purpose | `db.m6g.large`, `db.m7g.xlarge` | Balanced CPU/memory for production |
| Memory optimised | `db.r6g.large`, `db.r7g.2xlarge`, `db.x2g` | Cache-heavy or large working sets |

Storage options (EBS-backed for non-Aurora engines):

| Type | Characteristics |
|------|-----------------|
| General Purpose SSD (`gp3`, `gp2`) | Default choice; `gp3` lets IOPS and throughput be set independently of size |
| Provisioned IOPS SSD (`io1`, `io2`) | Guaranteed IOPS for latency-sensitive workloads |
| Magnetic | Legacy, not recommended |

Storage can be grown (not shrunk) online, and **storage autoscaling** can add capacity automatically when free space runs low. Most engines support up to 64 TiB per instance (16 TiB for SQL Server). Other instance settings: engine version, DB subnet group, parameter group, option group, port, maintenance window, backup window, deletion protection.

### Security

- **Network isolation**: an RDS instance is launched into a **DB subnet group** (at least two subnets in different AZs) inside my VPC. Keep it in **private subnets** and set `PubliclyAccessible = false` so it has no public IP.
- **Security groups**: attach a VPC security group that only allows the database port (3306 MySQL/MariaDB, 5432 PostgreSQL, 1433 SQL Server, 1521 Oracle) from the **application tier's security group**, never from `0.0.0.0/0`.
- **Encryption at rest with KMS**: enabling encryption at creation time encrypts the instance, its automated backups, snapshots, read replicas and logs using an AWS-managed or customer-managed KMS key. It cannot be switched on later; to encrypt an existing unencrypted instance, take a snapshot, copy it with encryption and restore.
- **Encryption in transit with TLS**: every instance provides a server certificate (AWS RDS CA). Enforce TLS with the `rds.force_ssl=1` parameter on PostgreSQL or `require_secure_transport=ON` on MySQL/MariaDB.
- **IAM database authentication**: instead of a password, the app requests a short-lived (15 minute) token with `aws rds generate-db-auth-token` and connects with it over TLS. Supported for MySQL, MariaDB and PostgreSQL; removes passwords from config files.
- **Secrets Manager integration**: the master password can be generated, stored and automatically rotated by Secrets Manager.
- **IAM** controls who can create/modify/delete instances; the database's own users control access to the data; audit logs can be shipped to CloudWatch Logs.

### Backups

| Type | Automated backups | Manual snapshots |
|------|-------------------|------------------|
| Created by | RDS, daily during the backup window, plus transaction logs every 5 minutes | Me (console, CLI, Terraform) whenever needed |
| Retention | 1 to **35 days** (0 disables them); console default is 7 days | Kept **until I delete them**, even after the instance is deleted |
| Point-in-time restore | Yes - to any second within the retention period, up to about 5 minutes before now | No - restores to the moment of the snapshot |
| Use | Day-to-day protection, undo bad migrations | Before major upgrades, long-term archives, copying to another region/account |

Notes: a restore always creates a **new** DB instance (new endpoint); it never overwrites the existing one. Snapshots are stored in S3 (managed by RDS), can be copied across regions for DR, and can be shared with other accounts. On Multi-AZ instances backups are taken from the standby, so there is no I/O pause on the primary.

### Multi-AZ

Multi-AZ is about **high availability**, not performance.

- RDS keeps a **synchronous standby replica** in a different Availability Zone. Every write is committed on both the primary and the standby before being acknowledged.
- The application connects to a single **DNS endpoint**. During an AZ outage, instance failure, OS patching or instance type change, RDS **automatically fails over** to the standby and flips the DNS record - typically within 60 to 120 seconds. No connection string changes are needed; the app only needs to reconnect.
- The standby **cannot serve reads** (in the classic Multi-AZ instance deployment). The newer **Multi-AZ DB cluster** deployment (MySQL/PostgreSQL) has two readable standbys and faster failover.
- Aurora is Multi-AZ by design: storage spans three AZs and a replica can be promoted in under 30 seconds.
- Cost is roughly double a single-AZ instance because two instances run.

### Read replicas

Read replicas are about **scaling reads** (and DR), not availability of writes.

- Data is copied from the source using the engine's native **asynchronous replication**, so a replica can lag slightly behind (`ReplicaLag` metric in CloudWatch).
- Each replica has its **own endpoint**; the application sends `SELECT` queries (reports, dashboards, search) to replicas and writes to the primary.
- Up to **15 read replicas** per source instance (Aurora supports 15 Aurora Replicas sharing the same storage, with a single reader endpoint that load-balances across them).
- **Cross-region read replicas** put data closer to users in another region and provide a disaster-recovery copy.
- A replica can be **promoted** to a standalone, writable instance (used for DR or for migrations). Replicas can themselves be Multi-AZ.

| | Multi-AZ standby | Read replica |
|--|------------------|--------------|
| Replication | Synchronous | Asynchronous |
| Purpose | High availability / automatic failover | Read scaling, reporting, DR, cross-region |
| Readable | No (classic Multi-AZ) | Yes |
| Endpoint | Same as primary | Separate |
| Promotion | Automatic | Manual |

### RDS use cases

- Transactional applications that need joins, constraints and ACID: e-commerce order systems, ERP, CRM, banking.
- Lift-and-shift of existing MySQL/PostgreSQL/Oracle/SQL Server applications to AWS without rewriting SQL.
- Content management systems (WordPress, Drupal) and web frameworks (Django, Rails, Spring) with ORMs.
- Reporting and analytics on relational data via read replicas.

## Part 3 - DynamoDB vs RDS

| Aspect | DynamoDB | RDS |
|--------|----------|-----|
| Data model | NoSQL key-value / document | Relational (tables, rows, foreign keys) |
| Schema | Only the primary key is fixed | Strict schema defined up front |
| Query language | API calls / PartiQL; no joins | Full SQL with joins, aggregations, views, stored procedures |
| Scaling | Horizontal and automatic; practically unlimited | Vertical (bigger instance class) plus read replicas; writes limited to one primary (except Aurora features) |
| Performance | Consistent single-digit ms latency regardless of size | Depends on instance size, indexes and query design |
| Consistency | Eventually consistent by default, strongly consistent on request | Strong (ACID) by default |
| Transactions | Supported, limited to 100 items | Full multi-table transactions |
| Availability | Built in across 3 AZs, 99.99 % SLA (99.999 % with Global Tables) | Multi-AZ must be enabled; single-AZ instance has downtime on failure |
| Management | Zero servers; no maintenance windows | Managed, but instance class, storage, patch and backup windows still need decisions |
| Pricing | Per request (on-demand) or per capacity unit, plus storage | Per instance-hour plus storage and I/O; runs even when idle |
| Max record size | 400 KB per item | Large rows, BLOBs/TEXT in GB range |
| Backup | PITR + on-demand backups, no performance impact | Automated backups (up to 35 days) + manual snapshots |
| Typical use | Serverless apps, high-scale key lookups, sessions, IoT, state locks | Business apps with complex relationships and ad-hoc reporting |

### When to choose which

Choose **DynamoDB** when:

- Access patterns are known up front and are mostly key-based lookups or range queries on a sort key.
- Traffic is unpredictable or very high and I do not want to manage capacity (serverless/Lambda architectures).
- I need a table that is highly available and global with zero maintenance - e.g. the Terraform state-lock table, session storage, device telemetry.
- Each record is small (< 400 KB) and I do not need joins.

Choose **RDS** when:

- The data is naturally relational: many entities with relationships, foreign keys and referential integrity.
- Developers and analysts need **ad-hoc SQL**, complex joins, reporting and existing BI tools.
- I am migrating an existing application that already uses MySQL, PostgreSQL, Oracle or SQL Server.
- Strong transactional consistency across many tables is required (payments, inventory, bookings).

Many real systems use **both**: RDS as the system of record for orders and customers, and DynamoDB for high-velocity data such as sessions, carts, counters or event logs.

## CLI examples

```bash
# ---------- DynamoDB ----------

# Create the Orders table with a composite primary key, on-demand billing
aws dynamodb create-table \
  --table-name Orders \
  --attribute-definitions \
      AttributeName=CustomerID,AttributeType=S \
      AttributeName=OrderDate,AttributeType=S \
  --key-schema \
      AttributeName=CustomerID,KeyType=HASH \
      AttributeName=OrderDate,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST

# Insert an item (inline JSON)
aws dynamodb put-item --table-name Orders --item '{
  "CustomerID":  {"S": "CUST-1001"},
  "OrderDate":   {"S": "2026-10-07T09:30:00Z"},
  "OrderID":     {"S": "ORD-78421"},
  "Status":      {"S": "SHIPPED"},
  "TotalAmount": {"N": "2499.00"}
}'

# Query all orders of one customer, newest first
aws dynamodb query --table-name Orders \
  --key-condition-expression "CustomerID = :c" \
  --expression-attribute-values '{":c": {"S": "CUST-1001"}}' \
  --no-scan-index-forward

# Terraform state-lock table used by the S3 backend
aws dynamodb create-table --table-name terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST

# ---------- RDS ----------

# List DB instances in a compact table
aws rds describe-db-instances \
  --query "DBInstances[].{Id:DBInstanceIdentifier,Engine:Engine,Class:DBInstanceClass,Status:DBInstanceStatus,MultiAZ:MultiAZ,Endpoint:Endpoint.Address}" \
  --output table

# Create a small PostgreSQL instance in private subnets (dev/test)
aws rds create-db-instance \
  --db-instance-identifier devops-postgres \
  --engine postgres --engine-version 16 \
  --db-instance-class db.t4g.micro \
  --allocated-storage 20 --storage-type gp3 \
  --master-username admin_user --manage-master-user-password \
  --db-subnet-group-name devops-private-subnets \
  --vpc-security-group-ids sg-0123456789abcdef0 \
  --no-publicly-accessible --storage-encrypted \
  --backup-retention-period 7

# Take a manual snapshot before a risky change
aws rds create-db-snapshot --db-instance-identifier devops-postgres \
  --db-snapshot-identifier devops-postgres-before-migration
```

## Terraform snippet

```hcl
# DynamoDB table for Terraform state locking
resource "aws_dynamodb_table" "tf_locks" {
  name         = "terraform-locks"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }
}

# Small RDS PostgreSQL instance in private subnets
resource "aws_db_instance" "postgres" {
  identifier             = "devops-postgres"
  engine                 = "postgres"
  engine_version         = "16"
  instance_class         = "db.t4g.micro"
  allocated_storage      = 20
  storage_type           = "gp3"
  storage_encrypted      = true
  db_subnet_group_name   = aws_db_subnet_group.private.name
  vpc_security_group_ids = [aws_security_group.db.id]
  publicly_accessible    = false
  multi_az               = false          # true for production
  backup_retention_period = 7
  username               = "admin_user"
  manage_master_user_password = true      # password stored in Secrets Manager
  skip_final_snapshot    = true           # false for production
}
```

## References

DynamoDB Developer Guide: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Introduction.html | DynamoDB read/write capacity: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/capacity-mode.html | RDS User Guide: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Welcome.html | RDS Multi-AZ: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.MultiAZ.html | RDS read replicas: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_ReadRepl.html | RDS backups: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_WorkingWithAutomatedBackups.html
