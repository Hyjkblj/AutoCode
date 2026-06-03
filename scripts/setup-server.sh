#!/bin/bash
# AutoCode Server Setup Script
# Usage: ./scripts/setup-server.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_DIR/.env.prod"

echo "========================================="
echo "AutoCode Server Setup"
echo "========================================="
echo ""

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "[!] Docker not found. Installing..."
    curl -fsSL https://get.docker.com | sh
    echo "[OK] Docker installed"
else
    echo "[OK] Docker found: $(docker --version)"
fi

# Check Docker Compose
if ! docker compose version &> /dev/null; then
    echo "[!] Docker Compose not found"
    exit 1
else
    echo "[OK] Docker Compose found: $(docker compose version --short)"
fi

# Generate .env.prod if not exists
if [ -f "$ENV_FILE" ]; then
    echo "[!] .env.prod already exists. Skipping generation."
    echo "    To regenerate, delete it first: rm $ENV_FILE"
else
    echo ""
    echo "Generating secure passwords..."

    MYSQL_ROOT_PASSWORD=$(openssl rand -base64 24)
    MYSQL_PASSWORD=$(openssl rand -base64 24)
    REDIS_PASSWORD=$(openssl rand -base64 24)
    JWT_SECRET=$(openssl rand -base64 48)
    AGENT_TOKEN=$(openssl rand -base64 32)
    GRAFANA_PASSWORD=$(openssl rand -base64 16)

    cat > "$ENV_FILE" <<EOF
# AutoCode Production Environment Variables
# Generated: $(date -Iseconds)

# ─── MySQL ──────────────────────────────────────────────────────
MYSQL_ROOT_PASSWORD=${MYSQL_ROOT_PASSWORD}
MYSQL_PASSWORD=${MYSQL_PASSWORD}

# ─── Redis ──────────────────────────────────────────────────────
REDIS_PASSWORD=${REDIS_PASSWORD}

# ─── JWT ────────────────────────────────────────────────────────
JWT_SECRET=${JWT_SECRET}

# ─── Agent ──────────────────────────────────────────────────────
AGENT_TOKEN=${AGENT_TOKEN}

# ─── LLM API ────────────────────────────────────────────────────
ARK_API_KEY=
OPENAI_API_KEY=
LLM_CONFIG_PATH=configs/doubao-seed-2.0-code-high-perf.json

# ─── Grafana ────────────────────────────────────────────────────
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
EOF

    chmod 600 "$ENV_FILE"
    echo "[OK] Generated .env.prod with secure passwords"
    echo ""
    echo "========================================="
    echo "IMPORTANT: Save these credentials!"
    echo "========================================="
    echo ""
    echo "MySQL Root Password:  ${MYSQL_ROOT_PASSWORD}"
    echo "MySQL App Password:   ${MYSQL_PASSWORD}"
    echo "Redis Password:       ${REDIS_PASSWORD}"
    echo "JWT Secret:           ${JWT_SECRET}"
    echo "Agent Token:          ${AGENT_TOKEN}"
    echo "Grafana Password:     ${GRAFANA_PASSWORD}"
    echo ""
    echo "These are also saved in: ${ENV_FILE}"
    echo ""
fi

# Start services
echo ""
echo "Starting services..."
cd "$PROJECT_DIR"
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d

echo ""
echo "Waiting for services to start..."
sleep 30

echo ""
echo "========================================="
echo "Service Status"
echo "========================================="
docker compose -f docker-compose.prod.yml ps

echo ""
echo "========================================="
echo "Setup Complete!"
echo "========================================="
echo ""
echo "Access points:"
echo "  Gateway:     http://$(hostname -I | awk '{print $1}'):8080"
echo "  Grafana:     http://$(hostname -I | awk '{print $1}'):3000"
echo "  Prometheus:  http://$(hostname -I | awk '{print $1}'):9090"
echo ""
echo "Health check:"
echo "  curl http://localhost:8080/actuator/health"
