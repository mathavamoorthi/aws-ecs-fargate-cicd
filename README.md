# DevOps Project 1 — Dockerized Flask app on AWS ECS Fargate

Production-style deployment of a containerized Flask app on AWS with a full CI/CD pipeline.

**Phase 1 (this branch):** infrastructure provisioned manually via the AWS Console (ClickOps). CI/CD via GitHub Actions.
**Phase 2 (upcoming):** the same infrastructure re-created as Terraform code with S3/DynamoDB remote state.

---

## Architecture

```
GitHub push → GitHub Actions → ECR (image) → ECS Fargate ← ALB ← Internet
                                                  │
                                                  └─→ RDS Postgres
```

- **VPC:** 10.0.0.0/16, 2 public + 2 private subnets across 2 AZs
- **Compute:** ECS Fargate (private subnets)
- **Ingress:** Application Load Balancer (public subnets)
- **Data:** RDS Postgres 16, db.t4g.micro (private subnets, encrypted)
- **Registry:** ECR
- **Auth:** GitHub OIDC → IAM role (no long-lived AWS keys)
- **Logs:** CloudWatch

## Endpoints

| Path      | Purpose                       |
|-----------|-------------------------------|
| `/`       | Hello + version               |
| `/health` | ALB target-group health check |
| `/db`     | Verifies DB connectivity      |

## Local development

```bash
docker compose up --build
curl http://localhost:8080/
curl http://localhost:8080/db
```

## CI/CD

- **PR workflow** (`.github/workflows/pr.yml`) — lint (flake8) + unit tests (pytest)
- **Deploy workflow** (`.github/workflows/deploy.yml`) — on push to `main`: build image → push to ECR → update ECS task definition → rolling deploy

## Cost

Full stack running 24/7 in `ap-south-1` is ~$60/month (NAT Gateway dominates). `terraform destroy` when not demoing keeps total spend under $10.

## Repo layout

```
app/                 Flask app + Dockerfile + tests
.github/workflows/   CI/CD pipelines
terraform/           (Phase 2) infrastructure as code
docs/                Architecture, decisions, migration story
```
