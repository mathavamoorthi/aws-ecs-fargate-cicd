# Dockerized Flask app on AWS ECS Fargate

Production-style deployment of a containerized Flask app on AWS with a full CI/CD pipeline.

---

## Architecture
```
GitHub push → GitHub Actions → ECR (image) → ECS Fargate ← ALB ← Internet
                                                  │
                                                  └─→ RDS Postgres
```

- **VPC:** 10.0.0.0/16, 2 public + 2 private subnets across 2 AZs
- **Compute:** ECS Fargate (ingress restricted to the ALB security group)
- **Ingress:** Application Load Balancer (public subnets)
- **Data:** RDS Postgres 16, db.t4g.micro (private subnets, encrypted)
- **Secrets:** SSM Parameter Store, injected at task start
- **Registry:** ECR
- **Auth:** GitHub OIDC → IAM role (no long-lived AWS keys)
- **Logs:** CloudWatch

Full resource configuration and design decisions: [docs/infrastructure.md](docs/infrastructure.md)

## Endpoints

| Path      | Purpose                       |
|-----------|-------------------------------|
| `/`       | Landing page                  |
| `/api`    | Version and host info (JSON)  |
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
