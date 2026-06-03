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
    echo "Generating .env.prod with default passwords..."

    cat > "$ENV_FILE" <<EOF
# AutoCode Production Environment Variables
# Generated: $(date -Iseconds)

# ─── MySQL ──────────────────────────────────────────────────────
MYSQL_ROOT_PASSWORD=000000
MYSQL_PASSWORD=000000

# ─── Redis ──────────────────────────────────────────────────────
REDIS_PASSWORD=000000

# ─── JWT ────────────────────────────────────────────────────────
JWT_SECRET=autocode-dev-jwt-secret-which-is-at-least-32bytes-long

# ─── Agent ──────────────────────────────────────────────────────
AGENT_TOKEN=agent-dev-token-000000

# ─── LLM API ────────────────────────────────────────────────────
ARK_API_KEY=
OPENAI_API_KEY=
LLM_CONFIG_PATH=configs/doubao-seed-2.0-code-high-perf.json

# ─── Grafana ────────────────────────────────────────────────────
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=000000
EOF

    chmod 600 "$ENV_FILE"
    echo "[OK] Generated .env.prod"
    echo ""
    echo "========================================="
    echo "Default passwords: 000000"
    echo "Change them in production!"
    echo "========================================="
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
