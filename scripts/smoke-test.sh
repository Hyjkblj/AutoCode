#!/bin/bash
# AutoCode post-deployment smoke test
# Usage: BASE_URL=https://autocode.example.com ./smoke-test.sh
# Requires: curl, jq

set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8080}"
PASS=0
FAIL=0

check() {
    local name="$1"
    local url="$2"
    local expected_status="${3:-200}"

    status=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")
    if [ "$status" = "$expected_status" ]; then
        echo "  [PASS] $name (HTTP $status)"
        PASS=$((PASS + 1))
    else
        echo "  [FAIL] $name (expected HTTP $expected_status, got HTTP $status)"
        FAIL=$((FAIL + 1))
    fi
}

echo "========================================="
echo "AutoCode Smoke Test"
echo "Target: $BASE_URL"
echo "Time:   $(date -Iseconds)"
echo "========================================="
echo ""

echo "--- Infrastructure ---"
check "Gateway health"       "$BASE_URL/actuator/health" 200
check "Control Plane health" "http://localhost:8058/actuator/health" 200 2>/dev/null || echo "  [SKIP] Control Plane not directly accessible"
check "Gateway readiness"    "$BASE_URL/actuator/health/readiness" 200

echo ""
echo "--- Security ---"
check "Actuator requires auth" "$BASE_URL/actuator/env" 401 2>/dev/null || \
check "Actuator requires auth" "$BASE_URL/actuator/env" 403 2>/dev/null || \
echo "  [WARN] Actuator may be unprotected"

echo ""
echo "--- API Endpoints ---"
check "API tasks endpoint"   "$BASE_URL/api/tasks" 401 2>/dev/null || \
check "API tasks endpoint"   "$BASE_URL/api/tasks" 403 2>/dev/null || \
check "API tasks endpoint"   "$BASE_URL/api/tasks" 200

check "OpenAPI spec"         "$BASE_URL/v3/api-docs" 200 2>/dev/null || \
echo "  [SKIP] OpenAPI not available at gateway level"

echo ""
echo "--- WebSocket ---"
WS_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Upgrade: websocket" -H "Connection: Upgrade" \
    -H "Sec-WebSocket-Version: 13" -H "Sec-WebSocket-Key: dGVzdA==" \
    "$BASE_URL/ws" 2>/dev/null || echo "000")
if [ "$WS_STATUS" = "101" ] || [ "$WS_STATUS" = "401" ]; then
    echo "  [PASS] WebSocket endpoint responds (HTTP $WS_STATUS)"
    PASS=$((PASS + 1))
else
    echo "  [FAIL] WebSocket endpoint (HTTP $WS_STATUS)"
    FAIL=$((FAIL + 1))
fi

echo ""
echo "========================================="
echo "Results: $PASS passed, $FAIL failed"
echo "========================================="

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
