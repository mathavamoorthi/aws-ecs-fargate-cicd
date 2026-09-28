# Infrastructure

AWS infrastructure for the application, region `ap-south-1`. Provisioned manually for the initial release; a Terraform implementation is planned.

## Architecture

```
                        Internet
                           │
                  ┌────────▼────────┐
                  │   ALB  :80      │  public subnets (2 AZ)
                  └────────┬────────┘
                           │  tcp/8080 from alb-sg only
                  ┌────────▼────────┐
                  │  ECS Fargate    │  public subnets, ingress restricted by SG
                  └────────┬────────┘
                           │  tcp/5432 from ecs-sg only
                  ┌────────▼────────┐
                  │ RDS PostgreSQL  │  private subnets, no public access
                  └─────────────────┘

GitHub Actions ──OIDC──▶ IAM role ──▶ ECR ──▶ ECS rolling deployment
```

## Resource inventory

| Resource | Name |
|---|---|
| ECR repository | `devops-project-1` |
| VPC | `devops-project-1-vpc` (`10.0.0.0/16`) |
| Security groups | `devops-project-1-alb-sg`, `devops-project-1-ecs-sg`, `devops-project-1-rds-sg` |
| DB subnet group | `devops-project-1-db-subnets` |
| RDS instance | `devops-project-1-db` |
| SSM parameter | `/devops-project-1/db-pass` |
| CloudWatch log group | `/ecs/devops-project-1` |
| ECS cluster | `devops-project-1-cluster` |
| Task definition | `devops-project-1-task` |
| Target group | `devops-project-1-tg` |
| Load balancer | `devops-project-1-alb` |
| ECS service | `devops-project-1-svc` |
| IAM roles | `github-actions-deploy`, `ecsTaskExecutionRole` |

Names referenced by `.github/workflows/deploy.yml` (ECR repository, cluster, service, task definition family, container name `app`) must match exactly.

## Provisioning

### 1. CI/CD access

**ECR repository** `devops-project-1`
- Tag mutability: mutable (`latest` is moved on each release; deployments pin the commit SHA tag)
- Lifecycle rule: expire images when count exceeds 10
- Basic scanning on push

**OIDC identity provider**
- URL `https://token.actions.githubusercontent.com`, audience `sts.amazonaws.com`

**IAM role** `github-actions-deploy`
- Trust policy: [`iam/github-trust-policy.json`](iam/github-trust-policy.json) — restricted to `main` of this repository
- Inline policy: [`iam/github-deploy-policy.json`](iam/github-deploy-policy.json) — ECR push to this repository, ECS task definition/service update, `iam:PassRole` on the execution role
- Role ARN stored as GitHub Actions secret `AWS_DEPLOY_ROLE_ARN`

### 2. Network

**VPC** (VPC-and-more wizard)

| Setting | Value |
|---|---|
| CIDR | `10.0.0.0/16` |
| Availability Zones | 2 (`ap-south-1a`, `ap-south-1b`) |
| Public subnets | `10.0.0.0/20`, `10.0.16.0/20` |
| Private subnets | `10.0.128.0/20`, `10.0.144.0/20` |
| NAT gateways | none |
| VPC endpoints | none |
| DNS hostnames / resolution | enabled |

**Security groups** (all in `devops-project-1-vpc`, default egress)

| Group | Inbound |
|---|---|
| `devops-project-1-alb-sg` | tcp/80 from `0.0.0.0/0` |
| `devops-project-1-ecs-sg` | tcp/8080 from `devops-project-1-alb-sg` |
| `devops-project-1-rds-sg` | tcp/5432 from `devops-project-1-ecs-sg` |

### 3. Database

**DB subnet group** `devops-project-1-db-subnets` — both private subnets.

**RDS instance** `devops-project-1-db`

| Setting | Value |
|---|---|
| Engine | PostgreSQL 16.x |
| Class | `db.t4g.micro`, Single-AZ |
| Storage | gp3 20 GiB, autoscaling disabled |
| Master user | `appuser` |
| Initial database | `appdb` |
| Subnet group / SG | `devops-project-1-db-subnets` / `devops-project-1-rds-sg` |
| Public access | no |
| Encryption | enabled (AWS managed key) |
| Backup retention | 1 day |

**SSM parameter** `/devops-project-1/db-pass` — SecureString, `alias/aws/ssm`, value = master password.

### 4. Compute

**CloudWatch log group** `/ecs/devops-project-1`, retention 7 days.

**Execution role** `ecsTaskExecutionRole`
- Managed policy `AmazonECSTaskExecutionRolePolicy`
- Inline policy [`iam/ecs-execution-extra-policy.json`](iam/ecs-execution-extra-policy.json) — `ssm:GetParameters` on `/devops-project-1/*`, `logs:CreateLogGroup`

No task role is attached; the application does not call AWS APIs.

**ECS cluster** `devops-project-1-cluster` — Fargate only, Container Insights disabled.

**Task definition** `devops-project-1-task`

| Setting | Value |
|---|---|
| Launch type / platform | Fargate, Linux/X86_64 |
| Size | 0.25 vCPU / 0.5 GB |
| Container | `app`, image `<ACCOUNT_ID>.dkr.ecr.ap-south-1.amazonaws.com/devops-project-1:<tag>`, port 8080/tcp |
| Logging | awslogs → `/ecs/devops-project-1`, prefix `ecs` |

| Variable | Source |
|---|---|
| `DB_HOST` | RDS endpoint |
| `DB_NAME` | `appdb` |
| `DB_USER` | `appuser` |
| `DB_PASS` | `valueFrom` SSM parameter ARN |
| `APP_VERSION` | set to the commit SHA by the deploy workflow |

### 5. Load balancing

**Target group** `devops-project-1-tg`

| Setting | Value |
|---|---|
| Target type | IP |
| Protocol / port | HTTP / 8080 |
| Health check | `GET /health`, interval 15 s, healthy threshold 2 |
| Deregistration delay | 30 s |

**Application Load Balancer** `devops-project-1-alb` — internet-facing, both public subnets, `devops-project-1-alb-sg`, listener HTTP:80 → `devops-project-1-tg`.

### 6. Service

**ECS service** `devops-project-1-svc`

| Setting | Value |
|---|---|
| Launch type | Fargate (LATEST) |
| Desired count | 1 |
| Deployment | rolling, min 100% / max 200% |
| Circuit breaker | enabled, rollback on failure |
| Subnets | public subnets, public IP enabled |
| Security group | `devops-project-1-ecs-sg` |
| Load balancer | `devops-project-1-alb` → `devops-project-1-tg`, container `app:8080` |
| Health check grace period | 60 s |

## Deployment

Pushes to `main` run `.github/workflows/deploy.yml`:

1. Assume `github-actions-deploy` via OIDC
2. Build the image and push `:<sha>` and `:latest` to ECR
3. Fetch the current `devops-project-1-task` definition
4. Render a new revision with the new image and `APP_VERSION=<sha>`
5. Update `devops-project-1-svc` and wait for service stability

Rollback: update the service to a previous task definition revision, or rely on the deployment circuit breaker.

## Design decisions

| Decision | Rationale | Production alternative |
|---|---|---|
| OIDC federation for CI | No long-lived credentials; role scoped to `main` of this repository | — |
| Fargate over EC2 | No host management or patching | EC2 capacity providers for cost at scale |
| Tasks in public subnets, no NAT | Avoids NAT gateway cost (~$40/month); ingress still restricted to the ALB security group | Private subnets with a NAT gateway per AZ, or VPC interface endpoints |
| Secrets via SSM `valueFrom` | Credentials never stored in the image, repository or task definition plaintext | Secrets Manager with rotation |
| `/health` independent of the database | A database outage should not cause every task to be replaced | — |
| Single-AZ RDS, 1 task | Cost | Multi-AZ RDS, ≥2 tasks with autoscaling |
| HTTP only | No custom domain | ACM certificate, HTTPS listener, HTTP→HTTPS redirect |

## Verification

- Service shows 1 running task; target group shows 1 healthy target
- `http://<alb-dns>/` returns 200; `http://<alb-dns>/db` returns `{"db": "up"}`
- Direct requests to the task's public IP on 8080 time out

## Troubleshooting

| Symptom | Cause |
|---|---|
| `sts:AssumeRoleWithWebIdentity` denied | Trust policy `sub` does not match repository/branch, or OIDC provider missing |
| `iam:PassRole` denied in deploy | Execution role name differs from the deploy policy |
| `CannotPullContainerError ... not found` | Image tag not present in ECR |
| `CannotPullContainerError` timeout | Task in private subnet or public IP disabled |
| `ResourceInitializationError: unable to pull secrets` | Execution role lacks `ssm:GetParameters`, or wrong parameter ARN |
| `exec format error` | Task definition architecture is ARM64; images are built for x86_64 |
| Targets unhealthy | `ecs-sg` missing 8080 from `alb-sg`, or wrong health check port/path |
| `/db` times out | `rds-sg` missing 5432 from `ecs-sg` |
| `/db` reports password failure | SSM value differs from RDS password; force a new deployment after updating |

## Teardown

Delete in order: ECS service → ECS cluster → load balancer → target group → RDS instance → VPC. Confirm no Elastic IPs remain allocated. ECR, IAM, SSM and CloudWatch resources incur negligible or no cost.
