# AutoCode Backend System Startup Guide

## Overview

This guide provides comprehensive instructions for starting the AutoCode Backend Upgrade 2.0 system using Docker Compose. The system consists of multiple services that must be started in the correct sequence to ensure proper initialization and health verification.

## System Architecture

The AutoCode backend system consists of the following core services:

- **Control Plane** (Port 8058): Java Spring Boot service managing task lifecycle and system coordination
- **Java Sandbox** (Port 18080): Secure execution environment with security policies
- **Python Agent**: Multi-agent orchestration system for code generation
- **Spring Cloud Gateway** (Port 8080): Unified API gateway for routing and security
- **MySQL** (Port 3306): Primary database for task and event persistence
- **Redis** (Port 6379): Caching, distributed locks, and event outbox
- **Observability Stack**:
  - **Prometheus** (Port 9090): Metrics collection and monitoring
  - **Grafana** (Port 3000): Dashboards and visualization
  - **Alertmanager** (Port 9093): Alert management and notifications

## Prerequisites

### System Requirements

- **Docker**: Version 20.10 or higher
- **Docker Compose**: Version 2.0 or higher
- **Available Memory**: Minimum 4GB RAM
- **Available Disk**: Minimum 2GB free space
- **Network Ports**: Ensure ports 3000, 3306, 6379, 8058, 8080, 9090, 9093, 18080 are available

### Environment Setup

1. **Clone the repository** (if not already done):
   ```bash
   git clone <repository-url>
   cd autocode-backend
   ```

2. **Create environment file**:
   ```bash
   cp .env.example .env
   ```

3. **Configure environment variables** in `.env`:
   ```bash
   # Required: Database passwords
   MYSQL_ROOT_PASSWORD=your_secure_mysql_root_password
   MVP_DB_PASSWORD=your_secure_mysql_password
   
   # Required: Redis password
   MVP_REDIS_PASSWORD=your_secure_redis_password
   
   # Required: JWT secret (minimum 32 characters)
   MVP_JWT_SECRET=your_jwt_secret_at_least_32_bytes_long_random_string
   
   # Required: Agent authentication
   MVP_AGENT_TOKEN=your_secure_agent_token
   
   # Required: Artifact download token
   MVP_ARTIFACTS_DOWNLOAD_SHARED_TOKEN=your_secure_shared_token
   
   # Required: LLM API key (choose one)
   ARK_API_KEY=your_ark_api_key
   # OR
   OPENAI_API_KEY=your_openai_api_key
   # OR
   ANTHROPIC_API_KEY=your_anthropic_api_key
   
   # Optional: Public hosting URL (for production deployments)
   MVP_ARTIFACTS_HOSTING_PUBLIC_BASE_URL=http://your-server.com:8058
   
   # Optional: LLM configuration
   LLM_CONFIG_PATH=configs/doubao-seed-2.0-code-high-perf.json
   WEB_TEMPLATE_PROMPT_MODE=direct
   
   # Optional: Grafana admin credentials
   GRAFANA_ADMIN_USER=admin
   GRAFANA_ADMIN_PASSWORD=your_secure_grafana_password
   ```

## Environment Variable Reference

### Required Variables

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `MYSQL_ROOT_PASSWORD` | MySQL root password | `changeme` | `SecureRootPass123!` |
| `MVP_DB_PASSWORD` | MySQL application user password | `changeme` | `SecureDbPass123!` |
| `MVP_REDIS_PASSWORD` | Redis authentication password | `changeme` | `SecureRedisPass123!` |
| `MVP_JWT_SECRET` | JWT signing secret (≥32 chars) | `your-jwt-secret-at-least-32-bytes-long` | `super-secure-jwt-secret-key-32-chars-min` |
| `MVP_AGENT_TOKEN` | Agent authentication token | `agent-dev-token` | `secure-agent-token-123` |
| `MVP_ARTIFACTS_DOWNLOAD_SHARED_TOKEN` | Artifact download token | None | `secure-download-token-456` |

### LLM Configuration (Choose One)

| Variable | Description | Provider |
|----------|-------------|----------|
| `ARK_API_KEY` | Volcano Engine Ark API key | ByteDance |
| `OPENAI_API_KEY` | OpenAI API key | OpenAI |
| `ANTHROPIC_API_KEY` | Anthropic Claude API key | Anthropic |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MVP_ARTIFACTS_HOSTING_PUBLIC_BASE_URL` | Public URL for artifact hosting | Empty |
| `LLM_CONFIG_PATH` | LLM configuration file path | `configs/doubao-seed-2.0-code-high-perf.json` |
| `WEB_TEMPLATE_PROMPT_MODE` | Template prompt mode | `direct` |
| `GRAFANA_ADMIN_USER` | Grafana admin username | `admin` |
| `GRAFANA_ADMIN_PASSWORD` | Grafana admin password | `changeme` |

## Startup Sequence

### Method 1: Full Platform Stack (Recommended)

Start all services including observability stack:

```bash
# Start all platform services
docker compose --profile platform up -d

# Monitor startup progress
docker compose logs -f
```

### Method 2: Minimal Fullstack

Start core services without observability:

```bash
# Start core fullstack services
docker compose --profile fullstack up -d

# Monitor startup progress
docker compose logs -f
```

### Method 3: Step-by-Step Startup

For debugging or controlled startup:

```bash
# Step 1: Start infrastructure services
docker compose up -d mysql redis

# Step 2: Wait for infrastructure health
docker compose ps
# Wait until mysql and redis show "healthy" status

# Step 3: Start control plane
docker compose up -d control-plane

# Step 4: Wait for control plane health
docker compose logs control-plane
# Wait for "Started ControlPlaneApplication" message

# Step 5: Start execution services
docker compose up -d pc-agent-java python-agent

# Step 6: Start gateway (platform profile only)
docker compose --profile platform up -d gateway

# Step 7: Start observability stack (platform profile only)
docker compose --profile platform up -d prometheus grafana alertmanager
```

## Health Verification

### Automated Health Checks

The system includes built-in health checks for all services. Monitor health status:

```bash
# Check all service health
docker compose ps

# Expected output should show "healthy" for all services:
# mvp-mysql        healthy
# mvp-redis        healthy  
# mvp-control-plane healthy
# mvp-gateway      healthy (if using platform profile)
```

### Manual Health Verification

Verify each service is responding correctly:

#### 1. Control Plane Health (Port 8058)
```bash
# Health endpoint should respond within 2 seconds
curl -f http://localhost:8058/actuator/health

# Expected response:
# {"status":"UP","components":{"db":{"status":"UP"},"redis":{"status":"UP"}}}
```

#### 2. Java Sandbox Health (Port 18080)
```bash
# Sandbox health with security policies active
curl -f http://localhost:18080/sandbox/health

# Expected response:
# {"status":"UP","securityPolicies":"ACTIVE","allowedPrefixes":["/workspace"]}
```

#### 3. Spring Cloud Gateway Health (Port 8080)
```bash
# Gateway health with routing configuration
curl -f http://localhost:8080/healthz

# Expected response:
# {"status":"UP","upstreamServices":{"control-plane":"UP"}}
```

#### 4. Observability Stack Health

**Prometheus (Port 9090):**
```bash
curl -f http://localhost:9090/-/healthy
# Expected: Prometheus is Healthy.
```

**Grafana (Port 3000):**
```bash
curl -f http://localhost:3000/api/health
# Expected: {"commit":"...","database":"ok","version":"..."}
```

**Alertmanager (Port 9093):**
```bash
curl -f http://localhost:9093/-/healthy
# Expected: Alertmanager is Healthy.
```

### Service Startup Timing

Expected startup sequence and timing:

1. **MySQL & Redis**: 10-30 seconds (depending on first-time initialization)
2. **Control Plane**: 15-45 seconds (includes database migration)
3. **Java Sandbox**: 10-20 seconds
4. **Python Agent**: 5-15 seconds
5. **Gateway**: 5-10 seconds
6. **Observability Stack**: 10-30 seconds

**Total System Startup Time**: 60-120 seconds for full platform stack

## Troubleshooting

### Common Issues

#### 1. Port Conflicts
**Symptom**: Services fail to start with "port already in use" errors
**Solution**:
```bash
# Check port usage
netstat -tulpn | grep -E ':(3000|3306|6379|8058|8080|9090|9093|18080)'

# Stop conflicting services or change ports in docker-compose.yml
```

#### 2. Database Connection Issues
**Symptom**: Control plane fails with database connection errors
**Solution**:
```bash
# Check MySQL health
docker compose logs mysql

# Verify credentials in .env file
# Restart MySQL if needed
docker compose restart mysql
```

#### 3. Memory Issues
**Symptom**: Services crash with OutOfMemory errors
**Solution**:
```bash
# Check available memory
free -h

# Increase Docker memory limits or reduce concurrent services
# Consider using fullstack profile instead of platform profile
```

#### 4. LLM API Issues
**Symptom**: Python agent fails with LLM connection errors
**Solution**:
```bash
# Verify API key in .env file
# Check LLM service status
# Review python-agent logs
docker compose logs python-agent
```

### Recovery Procedures

#### System Restart After Failure
```bash
# Stop all services
docker compose down

# Clean up if needed (WARNING: removes data)
docker compose down -v

# Restart with fresh state
docker compose --profile platform up -d
```

#### Partial Service Recovery
```bash
# Restart specific service
docker compose restart control-plane

# Check logs for errors
docker compose logs control-plane

# Verify health after restart
curl -f http://localhost:8058/actuator/health
```

## Performance Optimization

### Resource Allocation

**Recommended Docker Settings:**
- Memory: 4GB minimum, 8GB recommended
- CPU: 2 cores minimum, 4 cores recommended
- Disk: SSD recommended for database performance

### Database Optimization

**MySQL Configuration** (add to docker-compose.yml if needed):
```yaml
mysql:
  command: >
    --innodb-buffer-pool-size=512M
    --max-connections=100
    --innodb-log-file-size=128M
```

### Redis Optimization

**Redis Configuration** (add to docker-compose.yml if needed):
```yaml
redis:
  command: >
    redis-server
    --requirepass ${MVP_REDIS_PASSWORD:-changeme}
    --maxmemory 256mb
    --maxmemory-policy allkeys-lru
```

## Monitoring and Observability

### Accessing Dashboards

- **Grafana**: http://localhost:3000 (admin/changeme)
- **Prometheus**: http://localhost:9090
- **Alertmanager**: http://localhost:9093

### Key Metrics to Monitor

1. **System Health**: Service uptime and response times
2. **Task Processing**: Task creation, execution, and completion rates
3. **Event Reliability**: Event delivery success and retry rates
4. **Resource Usage**: CPU, memory, and disk utilization
5. **Error Rates**: Application errors and failure patterns

### Log Aggregation

View logs from all services:
```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f control-plane

# Filter by time
docker compose logs --since 1h control-plane
```

## Security Considerations

### Network Security
- All services run in isolated Docker network
- Only necessary ports are exposed to host
- Internal service communication uses container names

### Authentication
- JWT-based authentication for API access
- Agent token authentication for service communication
- Database and Redis password protection

### Data Protection
- Sensitive data encrypted in transit
- Database credentials managed via environment variables
- Artifact access controlled via shared tokens

## Maintenance

### Regular Tasks

1. **Log Rotation**: Monitor and rotate Docker logs
2. **Database Backup**: Regular MySQL backups
3. **Security Updates**: Keep Docker images updated
4. **Performance Monitoring**: Review Grafana dashboards

### Update Procedure

```bash
# Pull latest images
docker compose pull

# Restart with new images
docker compose --profile platform up -d

# Verify health after update
./scripts/smoke-test.ps1
```

## Support

### Log Collection for Support

```bash
# Collect all logs
docker compose logs > system-logs.txt

# Collect system information
docker compose ps > service-status.txt
docker system df > docker-usage.txt

# Package for support
tar -czf support-bundle.tar.gz system-logs.txt service-status.txt docker-usage.txt .env
```

### Emergency Procedures

**Complete System Reset** (WARNING: Destroys all data):
```bash
docker compose down -v
docker system prune -a
# Reconfigure .env file
docker compose --profile platform up -d
```

---

**Document Version**: 1.0  
**Last Updated**: $(date)  
**Compatibility**: AutoCode Backend Upgrade 2.0