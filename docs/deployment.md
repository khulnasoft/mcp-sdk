# Deployment Guide

This guide covers deploying the MCP SDK in various environments, from development to production.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Development Deployment](#development-deployment)
- [Production Deployment](#production-deployment)
- [Docker Deployment](#docker-deployment)
- [Kubernetes Deployment](#kubernetes-deployment)
- [Cloud Deployment](#cloud-deployment)
- [Monitoring and Logging](#monitoring-and-logging)
- [Security Considerations](#security-considerations)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements

- **Python**: 3.11 or higher
- **Memory**: Minimum 2GB RAM, 4GB+ recommended
- **Storage**: Minimum 10GB free space
- **Network**: Internet connection for dependencies

### Dependencies

- **uv**: Python package manager (recommended)
- **Docker**: Container runtime (for containerized deployment)
- **Node.js**: 18+ (for frontend components, if applicable)

## Development Deployment

### Quick Start

```bash
# Clone the repository
git clone https://github.com/your-org/mcp-sdk.git
cd mcp-sdk

# Run the setup script
./scripts/setup-dev.sh

# Start the development server
make docs
```

### Manual Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
uv pip install -e ".[dev,docs]"

# Set up pre-commit hooks
uv pre-commit install

# Create environment file
cp .env.example .env
# Edit .env with your configuration

# Run tests
uv pytest tests/

# Start documentation server
uv run mkdocs serve --host 0.0.0.0
```

### Environment Configuration

Create a `.env` file:

```bash
# Environment
ENVIRONMENT=development
LOG_LEVEL=debug

# Database
DATABASE_URL=sqlite:///./dev.db

# Redis (for caching)
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=your-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-key-here

# MCP Server
MCP_HOST=localhost
MCP_PORT=8080
```

## Production Deployment

### Environment Setup

```bash
# Production environment
ENVIRONMENT=production
LOG_LEVEL=info

# Use PostgreSQL for production
DATABASE_URL=postgresql://user:password@localhost:5432/mcp_sdk

# Redis cluster
REDIS_URL=redis://redis-cluster:6379/0

# Security (use strong secrets)
SECRET_KEY=$(openssl rand -hex 32)
JWT_SECRET_KEY=$(openssl rand -hex 32)

# Performance
WORKERS=4
WORKER_CONNECTIONS=1000
MAX_REQUESTS=1000
MAX_REQUESTS_JITTER=100

# Monitoring
ENABLE_METRICS=true
METRICS_PORT=9090
```

### Application Server

Using Gunicorn:

```bash
# Install Gunicorn
uv pip install gunicorn

# Start the application
gunicorn mcp_sdk.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8080 \
  --access-logfile - \
  --error-logfile - \
  --log-level info \
  --max-requests 1000 \
  --max-requests-jitter 100
```

### Process Management

Using systemd:

```ini
# /etc/systemd/system/mcp-sdk.service
[Unit]
Description=MCP SDK Application
After=network.target

[Service]
Type=exec
User=mcp-sdk
Group=mcp-sdk
WorkingDirectory=/opt/mcp-sdk
Environment=PATH=/opt/mcp-sdk/.venv/bin
ExecStart=/opt/mcp-sdk/.venv/bin/gunicorn mcp_sdk.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8080
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl enable mcp-sdk
sudo systemctl start mcp-sdk
sudo systemctl status mcp-sdk
```

## Docker Deployment

### Build the Image

```bash
# Build production image
docker build -t mcp-sdk:latest --target production .

# Build with specific tag
docker build -t mcp-sdk:v1.0.0 --target production .
```

### Run with Docker Compose

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  app:
    build:
      context: .
      target: production
    ports:
      - "8080:8080"
    environment:
      - ENVIRONMENT=production
      - DATABASE_URL=postgresql://postgres:password@db:5432/mcp_sdk
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  db:
    image: postgres:15
    environment:
      POSTGRES_DB: mcp_sdk
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - app
    restart: unless-stopped

volumes:
  postgres_data:
```

Deploy:

```bash
# Deploy to production
docker-compose -f docker-compose.prod.yml up -d

# Check status
docker-compose -f docker-compose.prod.yml ps

# View logs
docker-compose -f docker-compose.prod.yml logs -f app
```

## Kubernetes Deployment

### Namespace and Config

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: mcp-sdk

---
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: mcp-sdk-config
  namespace: mcp-sdk
data:
  ENVIRONMENT: "production"
  LOG_LEVEL: "info"
  MCP_HOST: "0.0.0.0"
  MCP_PORT: "8080"

---
# k8s/secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: mcp-sdk-secrets
  namespace: mcp-sdk
type: Opaque
data:
  DATABASE_URL: <base64-encoded-database-url>
  REDIS_URL: <base64-encoded-redis-url>
  SECRET_KEY: <base64-encoded-secret-key>
  JWT_SECRET_KEY: <base64-encoded-jwt-secret>
```

### Deployment

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcp-sdk
  namespace: mcp-sdk
spec:
  replicas: 3
  selector:
    matchLabels:
      app: mcp-sdk
  template:
    metadata:
      labels:
        app: mcp-sdk
    spec:
      containers:
      - name: mcp-sdk
        image: mcp-sdk:latest
        ports:
        - containerPort: 8080
        envFrom:
        - configMapRef:
            name: mcp-sdk-config
        - secretRef:
            name: mcp-sdk-secrets
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
```

### Service and Ingress

```yaml
# k8s/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: mcp-sdk-service
  namespace: mcp-sdk
spec:
  selector:
    app: mcp-sdk
  ports:
  - port: 80
    targetPort: 8080
  type: ClusterIP

---
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: mcp-sdk-ingress
  namespace: mcp-sdk
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/rate-limit: "100"
spec:
  tls:
  - hosts:
    - api.your-domain.com
    secretName: mcp-sdk-tls
  rules:
  - host: api.your-domain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: mcp-sdk-service
            port:
              number: 80
```

### Deploy to Kubernetes

```bash
# Apply all configurations
kubectl apply -f k8s/

# Check deployment status
kubectl get pods -n mcp-sdk
kubectl get services -n mcp-sdk
kubectl get ingress -n mcp-sdk

# View logs
kubectl logs -f deployment/mcp-sdk -n mcp-sdk
```

## Cloud Deployment

### AWS Deployment

#### Using ECS

```yaml
# ecs-task-definition.json
{
  "family": "mcp-sdk",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "arn:aws:iam::account:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::account:role/ecsTaskRole",
  "containerDefinitions": [
    {
      "name": "mcp-sdk",
      "image": "your-account.dkr.ecr.region.amazonaws.com/mcp-sdk:latest",
      "portMappings": [
        {
          "containerPort": 8080,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "ENVIRONMENT",
          "value": "production"
        }
      ],
      "secrets": [
        {
          "name": "DATABASE_URL",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:mcp-sdk/db-url"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/mcp-sdk",
          "awslogs-region": "us-west-2",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

#### Deploy with Terraform

```hcl
# main.tf
resource "aws_ecs_cluster" "mcp_sdk" {
  name = "mcp-sdk"
}

resource "aws_ecs_task_definition" "mcp_sdk" {
  family                   = "mcp-sdk"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn           = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name  = "mcp-sdk"
      image = "${aws_ecr_repository.mcp_sdk.repository_url}:latest"
      portMappings = [
        {
          containerPort = 8080
          protocol      = "tcp"
        }
      ]
    }
  ])
}

resource "aws_ecs_service" "mcp_sdk" {
  name            = "mcp-sdk"
  cluster         = aws_ecs_cluster.mcp_sdk.id
  task_definition = aws_ecs_task_definition.mcp_sdk.arn
  desired_count   = 2
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.mcp_sdk.id]
    assign_public_ip = false
  }
}
```

### Google Cloud Platform

#### Cloud Run Deployment

```bash
# Build and push to Google Container Registry
gcloud builds submit --tag gcr.io/PROJECT-ID/mcp-sdk

# Deploy to Cloud Run
gcloud run deploy mcp-sdk \
  --image gcr.io/PROJECT-ID/mcp-sdk \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars ENVIRONMENT=production \
  --set-secrets DATABASE_URL=mcp-sdk-db-url:latest
```

### Azure Container Instances

```bash
# Create resource group
az group create --name mcp-sdk-rg --location eastus

# Deploy to ACI
az container create \
  --resource-group mcp-sdk-rg \
  --name mcp-sdk \
  --image your-registry.azurecr.io/mcp-sdk:latest \
  --cpu 1 \
  --memory 2 \
  --ports 8080 \
  --environment-variables ENVIRONMENT=production \
  --secure-environment-variables DATABASE_URL=$DATABASE_URL
```

## Monitoring and Logging

### Prometheus Metrics

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'mcp-sdk'
    static_configs:
      - targets: ['localhost:9090']
    metrics_path: /metrics
    scrape_interval: 5s
```

### Grafana Dashboard

```json
{
  "dashboard": {
    "title": "MCP SDK Dashboard",
    "panels": [
      {
        "title": "Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(http_requests_total[5m])",
            "legendFormat": "{{method}} {{endpoint}}"
          }
        ]
      },
      {
        "title": "Response Time",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))",
            "legendFormat": "95th percentile"
          }
        ]
      }
    ]
  }
}
```

### Structured Logging

```python
# logging configuration
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "stream": "ext://sys.stdout"
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "json",
            "filename": "/var/log/mcp-sdk/app.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5
        }
    },
    "root": {
        "level": "INFO",
        "handlers": ["console", "file"]
    }
}
```

## Security Considerations

### SSL/TLS Configuration

```nginx
# nginx.conf
server {
    listen 443 ssl http2;
    server_name api.your-domain.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
    ssl_prefer_server_ciphers off;

    location / {
        proxy_pass http://app:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Firewall Rules

```bash
# UFW configuration
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw deny 8080/tcp   # Block direct access to app
sudo ufw enable
```

### Security Headers

```python
# Add security headers middleware
app.add_middleware(SecurityHeadersMiddleware)
```

## Troubleshooting

### Common Issues

#### Application Won't Start

```bash
# Check logs
docker logs mcp-sdk
kubectl logs deployment/mcp-sdk -n mcp-sdk

# Check configuration
docker exec -it mcp-sdk env | grep -E "(DATABASE|REDIS)"
```

#### Database Connection Issues

```bash
# Test database connection
python -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine

async def test():
    engine = create_async_engine('postgresql://user:pass@host/db')
    async with engine.connect() as conn:
        result = await conn.execute('SELECT 1')
        print('Database connection successful')

asyncio.run(test())
"
```

#### Memory Issues

```bash
# Monitor memory usage
docker stats mcp-sdk
kubectl top pods -n mcp-sdk

# Check for memory leaks
python -m memory_profiler mcp_sdk/main.py
```

#### Performance Issues

```bash
# Profile application
python -m cProfile -o profile.stats mcp_sdk/main.py
python -c "
import pstats
p = pstats.Stats('profile.stats')
p.sort_stats('cumulative').print_stats(20)
"
```

### Health Checks

```bash
# Check application health
curl -f http://localhost:8080/health || echo "Health check failed"

# Check readiness
curl -f http://localhost:8080/ready || echo "Readiness check failed"

# Check metrics
curl http://localhost:9090/metrics
```

### Debug Mode

```bash
# Enable debug logging
export LOG_LEVEL=debug

# Run with debugger
python -m debugpy --listen 5678 --wait-for-client mcp_sdk/main.py
```

## Backup and Recovery

### Database Backup

```bash
# PostgreSQL backup
pg_dump -h localhost -U postgres mcp_sdk > backup_$(date +%Y%m%d).sql

# Restore backup
psql -h localhost -U postgres mcp_sdk < backup_20231201.sql
```

### Application Backup

```bash
# Backup configuration
tar -czf mcp-sdk-config-$(date +%Y%m%d).tar.gz \
  .env \
  docker-compose.yml \
  k8s/ \
  scripts/
```

This deployment guide provides comprehensive instructions for deploying the MCP SDK in various environments. Choose the deployment method that best fits your infrastructure and requirements.
