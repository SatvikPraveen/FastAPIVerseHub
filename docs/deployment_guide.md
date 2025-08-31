# Deployment Guide

**File Location: `docs/deployment_guide.md`**

## Deployment Options

### 1. Docker Deployment (Recommended)

### 2. Traditional Server Deployment

### 3. Cloud Deployment (AWS, GCP, Azure)

### 4. Container Orchestration (Kubernetes)

## Docker Deployment

### Prerequisites

- Docker installed
- Docker Compose installed
- Domain name (for production)
- SSL certificates (for HTTPS)

### Development Deployment

```bash
# Clone repository
git clone <repository-url>
cd FastAPIVerseHub

# Copy environment file
cp .env.example .env

# Edit environment variables
nano .env

# Start services
docker-compose up -d

# View logs
docker-compose logs -f app

# Stop services
docker-compose down
```

### Production Docker Setup

```yaml
# docker-compose.prod.yml
version: "3.8"

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=production
      - DATABASE_URL=postgresql://user:password@db:5432/fastapi_prod
      - REDIS_URL=redis://redis:6379
      - SECRET_KEY=${SECRET_KEY}
    depends_on:
      - db
      - redis
    volumes:
      - ./uploads:/app/uploads
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=fastapi_prod
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backups:/backups
    restart: unless-stopped
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    restart: unless-stopped
    command: redis-server --appendonly yes

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./nginx/ssl:/etc/nginx/ssl
      - ./uploads:/var/www/uploads
    depends_on:
      - app
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

### Nginx Configuration

```nginx
# nginx/nginx.conf
events {
    worker_connections 1024;
}

http {
    upstream fastapi {
        server app:8000;
    }

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

    server {
        listen 80;
        server_name your-domain.com www.your-domain.com;

        # Redirect HTTP to HTTPS
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name your-domain.com www.your-domain.com;

        # SSL Configuration
        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;

        # Security headers
        add_header X-Content-Type-Options nosniff;
        add_header X-Frame-Options DENY;
        add_header X-XSS-Protection "1; mode=block";
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";

        # File upload size
        client_max_body_size 100M;

        # API routes
        location /api/ {
            limit_req zone=api burst=20 nodelay;
            proxy_pass http://fastapi;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # WebSocket support
        location /api/v1/ws {
            proxy_pass http://fastapi;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Static files
        location /uploads/ {
            alias /var/www/uploads/;
            expires 1y;
            add_header Cache-Control "public, immutable";
        }

        # Health check
        location /health {
            proxy_pass http://fastapi;
            access_log off;
        }
    }
}
```

### Production Environment Variables

```bash
# .env.production
ENVIRONMENT=production
DEBUG=false

# Database
DATABASE_URL=postgresql://user:secure_password@db:5432/fastapi_prod

# Redis
REDIS_URL=redis://redis:6379

# Security
SECRET_KEY=your-super-secret-key-here-change-this
JWT_SECRET_KEY=your-jwt-secret-key-here

# Email
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# File Storage
UPLOAD_DIR=/app/uploads
MAX_FILE_SIZE=10485760  # 10MB

# External APIs
EXTERNAL_API_KEY=your-external-api-key

# Monitoring
SENTRY_DSN=your-sentry-dsn-here
```

## Traditional Server Deployment

### System Requirements

- Ubuntu 20.04+ or CentOS 8+
- Python 3.11+
- PostgreSQL 13+
- Redis 6+
- Nginx

### Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install python3.11 python3.11-venv python3.11-dev
sudo apt install postgresql postgresql-contrib
sudo apt install redis-server
sudo apt install nginx
sudo apt install certbot python3-certbot-nginx

# Create application user
sudo useradd -m -s /bin/bash fastapi
sudo usermod -aG sudo fastapi
```

### Application Setup

```bash
# Switch to app user
sudo su - fastapi

# Clone repository
git clone <repository-url> /home/fastapi/app
cd /home/fastapi/app

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e .

# Set up environment
cp .env.example .env
# Edit .env with production values

# Create uploads directory
mkdir -p uploads
chmod 755 uploads

# Run database migrations
alembic upgrade head
```

### Systemd Service

```ini
# /etc/systemd/system/fastapi.service
[Unit]
Description=FastAPI application
After=network.target postgresql.service redis.service

[Service]
Type=exec
User=fastapi
Group=fastapi
WorkingDirectory=/home/fastapi/app
Environment=PATH=/home/fastapi/app/venv/bin
ExecStart=/home/fastapi/app/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable fastapi
sudo systemctl start fastapi
sudo systemctl status fastapi
```

### SSL with Let's Encrypt

```bash
# Install SSL certificate
sudo certbot --nginx -d your-domain.com -d www.your-domain.com

# Auto-renewal
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

## Cloud Deployment

### AWS Deployment

#### Using AWS ECS

```yaml
# docker-compose.aws.yml
version: "3.8"

services:
  app:
    image: your-ecr-repo/fastapi-verse-hub:latest
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - SECRET_KEY=${SECRET_KEY}
    logging:
      driver: awslogs
      options:
        awslogs-group: /ecs/fastapi-app
        awslogs-region: us-west-2
        awslogs-stream-prefix: ecs
```

#### ECS Task Definition

```json
{
  "family": "fastapi-verse-hub",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::account:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::account:role/ecsTaskRole",
  "containerDefinitions": [
    {
      "name": "fastapi-app",
      "image": "your-account.dkr.ecr.region.amazonaws.com/fastapi-verse-hub:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "DATABASE_URL",
          "value": "postgresql://user:pass@rds-endpoint:5432/db"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/fastapi-app",
          "awslogs-region": "us-west-2",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": [
          "CMD-SHELL",
          "curl -f http://localhost:8000/health || exit 1"
        ],
        "interval": 30,
        "timeout": 5,
        "retries": 3
      }
    }
  ]
}
```

### Google Cloud Platform

#### Cloud Run Deployment

```yaml
# cloudbuild.yaml
steps:
  # Build the container image
  - name: "gcr.io/cloud-builders/docker"
    args:
      ["build", "-t", "gcr.io/$PROJECT_ID/fastapi-verse-hub:$COMMIT_SHA", "."]

  # Push the container image to Container Registry
  - name: "gcr.io/cloud-builders/docker"
    args: ["push", "gcr.io/$PROJECT_ID/fastapi-verse-hub:$COMMIT_SHA"]

  # Deploy container image to Cloud Run
  - name: "gcr.io/google.com/cloudsdktool/cloud-sdk"
    entrypoint: "gcloud"
    args:
      - "run"
      - "deploy"
      - "fastapi-verse-hub"
      - "--image"
      - "gcr.io/$PROJECT_ID/fastapi-verse-hub:$COMMIT_SHA"
      - "--region"
      - "us-central1"
      - "--platform"
      - "managed"
      - "--allow-unauthenticated"
```

### Azure Deployment

#### Container Instances

```bash
# Create resource group
az group create --name fastapi-rg --location eastus

# Create container instance
az container create \
  --resource-group fastapi-rg \
  --name fastapi-container \
  --image your-registry/fastapi-verse-hub:latest \
  --dns-name-label fastapi-unique-name \
  --ports 8000 \
  --environment-variables \
    DATABASE_URL="postgresql://user:pass@host:5432/db" \
    REDIS_URL="redis://host:6379"
```

## Kubernetes Deployment

### Deployment Configuration

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: fastapi-app
  labels:
    app: fastapi-app
spec:
  replicas: 3
  selector:
    matchLabels:
      app: fastapi-app
  template:
    metadata:
      labels:
        app: fastapi-app
    spec:
      containers:
        - name: fastapi-app
          image: your-registry/fastapi-verse-hub:latest
          ports:
            - containerPort: 8000
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: app-secrets
                  key: database-url
            - name: REDIS_URL
              valueFrom:
                secretKeyRef:
                  name: app-secrets
                  key: redis-url
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 30
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 5
          resources:
            requests:
              memory: "256Mi"
              cpu: "250m"
            limits:
              memory: "512Mi"
              cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: fastapi-service
spec:
  selector:
    app: fastapi-app
  ports:
    - protocol: TCP
      port: 80
      targetPort: 8000
  type: ClusterIP
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: fastapi-ingress
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
    - hosts:
        - your-domain.com
      secretName: fastapi-tls
  rules:
    - host: your-domain.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: fastapi-service
                port:
                  number: 80
```

### Secrets Configuration

```yaml
# k8s/secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: app-secrets
type: Opaque
data:
  database-url: <base64-encoded-database-url>
  redis-url: <base64-encoded-redis-url>
  secret-key: <base64-encoded-secret-key>
```

## Monitoring and Observability

### Health Checks

```python
# Add to app/main.py
@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "version": "1.0.0"
    }

@app.get("/ready")
async def readiness_check():
    # Check database connection
    try:
        db = next(get_db())
        db.execute("SELECT 1")
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"

    # Check Redis connection
    try:
        redis_client.ping()
        redis_status = "healthy"
    except Exception:
        redis_status = "unhealthy"

    return {
        "database": db_status,
        "redis": redis_status,
        "status": "ready" if all([db_status == "healthy", redis_status == "healthy"]) else "not_ready"
    }
```

### Logging Configuration

```python
# app/core/logging.py
import logging
import sys
from typing import Any, Dict
import json
import structlog

def setup_logging(level: str = "INFO", json_logs: bool = False):
    timestamper = structlog.processors.TimeStamper(fmt="ISO")

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if json_logs:
        processors = shared_processors + [structlog.processors.JSONRenderer()]
    else:
        processors = shared_processors + [structlog.dev.ConsoleRenderer()]

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper()),
    )
```

### Prometheus Metrics

```python
# app/middleware/metrics.py
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import time

REQUEST_COUNT = Counter('requests_total', 'Total requests', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('request_duration_seconds', 'Request duration')

class MetricsMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.time()

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                REQUEST_COUNT.labels(
                    method=scope["method"],
                    endpoint=scope["path"],
                    status=message["status"]
                ).inc()

                REQUEST_DURATION.observe(time.time() - start_time)

            await send(message)

        await self.app(scope, receive, send_wrapper)

@app.get("/metrics")
def get_metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

## Database Management

### Backup Scripts

```bash
#!/bin/bash
# scripts/backup_database.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups"
DB_NAME="fastapi_prod"
DB_USER="user"
DB_HOST="localhost"

# Create backup directory
mkdir -p $BACKUP_DIR

# Create backup
pg_dump -h $DB_HOST -U $DB_USER -d $DB_NAME > $BACKUP_DIR/backup_$DATE.sql

# Compress backup
gzip $BACKUP_DIR/backup_$DATE.sql

# Keep only last 7 days of backups
find $BACKUP_DIR -name "backup_*.sql.gz" -mtime +7 -delete

echo "Backup completed: backup_$DATE.sql.gz"
```

### Migration Management

```bash
# Run migrations in production
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "Add new table"

# Rollback migration
alembic downgrade -1
```

## Security Hardening

### Environment Variables

```bash
# Use secrets management
export SECRET_KEY=$(aws secretsmanager get-secret-value --secret-id prod/fastapi/secret-key --query SecretString --output text)
export DATABASE_URL=$(aws secretsmanager get-secret-value --secret-id prod/fastapi/database-url --query SecretString --output text)
```

### Security Headers

```python
# app/middleware/security.py
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
```

## Performance Optimization

### Connection Pooling

```python
# app/core/database.py
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True,
    pool_recycle=1800
)
```

### Caching

```python
# app/core/cache.py
import redis
from functools import wraps

redis_client = redis.from_url(REDIS_URL)

def cache_result(expire_time=300):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"

            # Try to get from cache
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)

            # Get result and cache it
            result = await func(*args, **kwargs)
            redis_client.setex(cache_key, expire_time, json.dumps(result, default=str))
            return result
        return wrapper
    return decorator
```

## Deployment Checklist

### Pre-deployment

- [ ] Update dependencies
- [ ] Run all tests
- [ ] Update documentation
- [ ] Backup database
- [ ] Review security settings
- [ ] Test in staging environment

### Deployment

- [ ] Deploy new version
- [ ] Run database migrations
- [ ] Verify health checks
- [ ] Test critical paths
- [ ] Monitor logs and metrics
- [ ] Rollback plan ready

### Post-deployment

- [ ] Verify all services running
- [ ] Check application metrics
- [ ] Monitor error rates
- [ ] Validate critical functionality
- [ ] Update monitoring dashboards
- [ ] Document changes

## Troubleshooting

### Common Issues

1. **Application won't start**

   - Check environment variables
   - Verify database connectivity
   - Check log files

2. **Database connection errors**

   - Verify credentials
   - Check network connectivity
   - Review connection pool settings

3. **High memory usage**

   - Check for memory leaks
   - Review connection pool size
   - Monitor background tasks

4. **Slow response times**
   - Check database query performance
   - Review caching strategy
   - Monitor resource usage

### Log Analysis

```bash
# View application logs
docker logs -f fastapi-app

# Follow nginx logs
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log

# PostgreSQL logs
tail -f /var/log/postgresql/postgresql-13-main.log
```
