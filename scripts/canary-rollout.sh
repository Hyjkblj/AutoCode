#!/usr/bin/env bash
# =============================================================================
# canary-rollout.sh — Manage canary deployments for Backend Upgrade 2.0
#
# Usage:
#   ./scripts/canary-rollout.sh <command> <component> [options]
#
# Commands:
#   capture-baseline  <component>           Capture current performance baseline
#   start-canary      <component>           Start canary at 5% traffic
#   increase-traffic  <component> <pct>     Increase canary traffic to <pct>%
#   complete-rollout  <component>           Complete rollout to 100%
#   rollback          <component>           Roll back to legacy path (0%)
#   status            <component>           Show current canary state
#   validate-performance <component>        Validate metrics against baseline
#
# Components:
#   langgraph_engine          LangGraph orchestration engine
#   new_backend_generator     Enhanced Flask/FastAPI generator
#   spring_cloud_gateway      Spring Cloud Gateway routing
#   artifact_microservice     Extracted Artifact Service
#   event_microservice        Extracted Event Service
#   approval_microservice     Extracted Approval Service
#   new_validation_gate       Enhanced validation gate
#   distributed_lock_v2       Updated distributed lock
#
# Environment variables:
#   REDIS_HOST      Redis host (default: localhost)
#   REDIS_PORT      Redis port (default: 6379)
#   REDIS_PASSWORD  Redis password (optional)
#   PROMETHEUS_URL  Prometheus base URL (default: http://localhost:9090)
#   BASELINE_DIR    Directory for baseline files (default: scripts/baselines)
#
# Validates: Requirements 11.3, 11.6, 11.7
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"
REDIS_PASSWORD="${REDIS_PASSWORD:-}"
PROMETHEUS_URL="${PROMETHEUS_URL:-http://localhost:9090}"
BASELINE_DIR="${BASELINE_DIR:-scripts/baselines}"

# Canary phase thresholds
PHASE_1_PCT=5
PHASE_2_PCT=25
PHASE_3_PCT=50
PHASE_4_PCT=100

# Health check settings
HEALTH_CHECK_RETRIES=3
HEALTH_CHECK_INTERVAL=5  # seconds

# Performance thresholds (relative to baseline)
MAX_LATENCY_MULTIPLIER=1.10   # P95 latency must not exceed baseline × 1.10
MAX_ERROR_RATE_DELTA=0.005    # Error rate must not exceed baseline + 0.5%
MIN_THROUGHPUT_RATIO=0.95     # Throughput must be at least 95% of baseline

# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'  # No colour

log_info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_success() { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ---------------------------------------------------------------------------
# Redis helpers
# ---------------------------------------------------------------------------

redis_cmd() {
    if [[ -n "${REDIS_PASSWORD}" ]]; then
        redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" -a "${REDIS_PASSWORD}" "$@" 2>/dev/null
    else
        redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" "$@" 2>/dev/null
    fi
}

redis_set() {
    local key="$1"
    local value="$2"
    redis_cmd SET "${key}" "${value}" > /dev/null
}

redis_get() {
    local key="$1"
    redis_cmd GET "${key}"
}

flag_key_enabled()    { echo "feature_flag:${1}:enabled"; }
flag_key_canary()     { echo "feature_flag:${1}:canary_percentage"; }
flag_key_updated_at() { echo "feature_flag:${1}:updated_at"; }
flag_key_updated_by() { echo "feature_flag:${1}:updated_by"; }

set_flag() {
    local component="$1"
    local enabled="$2"
    local canary_pct="$3"
    local updated_by="${4:-canary-rollout.sh}"
    local now
    now=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    redis_set "$(flag_key_enabled    "${component}")" "${enabled}"
    redis_set "$(flag_key_canary     "${component}")" "${canary_pct}"
    redis_set "$(flag_key_updated_at "${component}")" "${now}"
    redis_set "$(flag_key_updated_by "${component}")" "${updated_by}"
}

get_flag_state() {
    local component="$1"
    local enabled canary_pct updated_at updated_by
    enabled=$(redis_get "$(flag_key_enabled    "${component}")")
    canary_pct=$(redis_get "$(flag_key_canary  "${component}")")
    updated_at=$(redis_get "$(flag_key_updated_at "${component}")")
    updated_by=$(redis_get "$(flag_key_updated_by "${component}")")

    echo "  flag:              ${component}"
    echo "  enabled:           ${enabled:-<not set>}"
    echo "  canary_percentage: ${canary_pct:-<not set>}"
    echo "  updated_at:        ${updated_at:-<not set>}"
    echo "  updated_by:        ${updated_by:-<not set>}"
}

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

check_health() {
    local component="$1"
    local attempt=0

    log_info "Running health checks for component: ${component}"

    while [[ ${attempt} -lt ${HEALTH_CHECK_RETRIES} ]]; do
        attempt=$(( attempt + 1 ))

        # Check Control Plane
        if curl -sf "http://localhost:8058/actuator/health" > /dev/null 2>&1; then
            log_success "Control Plane health check passed (attempt ${attempt})"
        else
            log_warn "Control Plane health check failed (attempt ${attempt}/${HEALTH_CHECK_RETRIES})"
            if [[ ${attempt} -ge ${HEALTH_CHECK_RETRIES} ]]; then
                log_error "Control Plane health check failed after ${HEALTH_CHECK_RETRIES} attempts"
                return 1
            fi
            sleep "${HEALTH_CHECK_INTERVAL}"
            continue
        fi

        # Check Python Agent (Redis connectivity)
        if redis_cmd PING | grep -q "PONG"; then
            log_success "Redis health check passed"
        else
            log_warn "Redis health check failed (attempt ${attempt}/${HEALTH_CHECK_RETRIES})"
            if [[ ${attempt} -ge ${HEALTH_CHECK_RETRIES} ]]; then
                log_error "Redis health check failed after ${HEALTH_CHECK_RETRIES} attempts"
                return 1
            fi
            sleep "${HEALTH_CHECK_INTERVAL}"
            continue
        fi

        log_success "All health checks passed"
        return 0
    done

    return 1
}

# ---------------------------------------------------------------------------
# Prometheus metric helpers
# ---------------------------------------------------------------------------

query_prometheus() {
    local query="$1"
    curl -sf "${PROMETHEUS_URL}/api/v1/query" \
        --data-urlencode "query=${query}" \
        2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
results = data.get('data', {}).get('result', [])
if results:
    print(results[0]['value'][1])
else:
    print('0')
" 2>/dev/null || echo "0"
}

# ---------------------------------------------------------------------------
# Baseline capture
# ---------------------------------------------------------------------------

cmd_capture_baseline() {
    local component="$1"
    mkdir -p "${BASELINE_DIR}"
    local baseline_file="${BASELINE_DIR}/${component}-baseline.json"

    log_info "Capturing performance baseline for: ${component}"

    local p95_latency error_rate throughput
    p95_latency=$(query_prometheus 'histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))')
    error_rate=$(query_prometheus 'rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])')
    throughput=$(query_prometheus 'rate(http_requests_total[5m])')

    cat > "${baseline_file}" <<EOF
{
  "component": "${component}",
  "captured_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "metrics": {
    "p95_latency_seconds": ${p95_latency},
    "error_rate": ${error_rate},
    "throughput_rps": ${throughput}
  },
  "thresholds": {
    "max_p95_latency_seconds": $(echo "${p95_latency} * ${MAX_LATENCY_MULTIPLIER}" | bc -l 2>/dev/null || echo "1.0"),
    "max_error_rate": $(echo "${error_rate} + ${MAX_ERROR_RATE_DELTA}" | bc -l 2>/dev/null || echo "0.01"),
    "min_throughput_rps": $(echo "${throughput} * ${MIN_THROUGHPUT_RATIO}" | bc -l 2>/dev/null || echo "0")
  }
}
EOF

    log_success "Baseline captured to: ${baseline_file}"
    cat "${baseline_file}"
}

# ---------------------------------------------------------------------------
# Performance validation
# ---------------------------------------------------------------------------

cmd_validate_performance() {
    local component="$1"
    local baseline_file="${BASELINE_DIR}/${component}-baseline.json"

    if [[ ! -f "${baseline_file}" ]]; then
        log_warn "No baseline file found at ${baseline_file}. Run capture-baseline first."
        log_warn "Skipping performance validation."
        return 0
    fi

    log_info "Validating performance for: ${component}"

    local current_p95 current_error_rate current_throughput
    current_p95=$(query_prometheus 'histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))')
    current_error_rate=$(query_prometheus 'rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])')
    current_throughput=$(query_prometheus 'rate(http_requests_total[5m])')

    local max_p95 max_error_rate min_throughput
    max_p95=$(python3 -c "import json; d=json.load(open('${baseline_file}')); print(d['thresholds']['max_p95_latency_seconds'])" 2>/dev/null || echo "999")
    max_error_rate=$(python3 -c "import json; d=json.load(open('${baseline_file}')); print(d['thresholds']['max_error_rate'])" 2>/dev/null || echo "1")
    min_throughput=$(python3 -c "import json; d=json.load(open('${baseline_file}')); print(d['thresholds']['min_throughput_rps'])" 2>/dev/null || echo "0")

    local failed=0

    log_info "Current P95 latency:  ${current_p95}s  (max allowed: ${max_p95}s)"
    log_info "Current error rate:   ${current_error_rate}  (max allowed: ${max_error_rate})"
    log_info "Current throughput:   ${current_throughput} rps  (min required: ${min_throughput} rps)"

    if python3 -c "exit(0 if float('${current_p95}') <= float('${max_p95}') else 1)" 2>/dev/null; then
        log_success "P95 latency within threshold"
    else
        log_error "P95 latency EXCEEDS threshold: ${current_p95}s > ${max_p95}s"
        failed=1
    fi

    if python3 -c "exit(0 if float('${current_error_rate}') <= float('${max_error_rate}') else 1)" 2>/dev/null; then
        log_success "Error rate within threshold"
    else
        log_error "Error rate EXCEEDS threshold: ${current_error_rate} > ${max_error_rate}"
        failed=1
    fi

    if python3 -c "exit(0 if float('${current_throughput}') >= float('${min_throughput}') else 1)" 2>/dev/null; then
        log_success "Throughput within threshold"
    else
        log_error "Throughput BELOW threshold: ${current_throughput} rps < ${min_throughput} rps"
        failed=1
    fi

    if [[ ${failed} -ne 0 ]]; then
        log_error "Performance validation FAILED for ${component}"
        return 1
    fi

    log_success "Performance validation PASSED for ${component}"
    return 0
}

# ---------------------------------------------------------------------------
# Canary commands
# ---------------------------------------------------------------------------

cmd_start_canary() {
    local component="$1"

    log_info "Starting canary rollout for: ${component} at ${PHASE_1_PCT}%"

    if ! check_health "${component}"; then
        log_error "Health checks failed. Aborting canary start."
        exit 1
    fi

    set_flag "${component}" "true" "${PHASE_1_PCT}"
    log_success "Canary started: ${component} at ${PHASE_1_PCT}%"
    log_info "Monitor for at least 30 minutes before increasing traffic."
    log_info "Run: ./scripts/canary-rollout.sh validate-performance ${component}"
    log_info "Run: ./scripts/canary-rollout.sh increase-traffic ${component} ${PHASE_2_PCT}"
}

cmd_increase_traffic() {
    local component="$1"
    local target_pct="$2"

    if ! [[ "${target_pct}" =~ ^[0-9]+$ ]] || [[ "${target_pct}" -lt 1 ]] || [[ "${target_pct}" -gt 100 ]]; then
        log_error "Invalid percentage: ${target_pct}. Must be 1–100."
        exit 1
    fi

    log_info "Increasing canary traffic for: ${component} to ${target_pct}%"

    if ! check_health "${component}"; then
        log_error "Health checks failed. Refusing to increase traffic."
        log_warn "Run rollback if the issue persists: ./scripts/rollback.sh rollback ${component}"
        exit 1
    fi

    if ! cmd_validate_performance "${component}"; then
        log_error "Performance validation failed. Refusing to increase traffic."
        log_warn "Run rollback: ./scripts/rollback.sh rollback ${component}"
        exit 1
    fi

    set_flag "${component}" "true" "${target_pct}"
    log_success "Traffic increased: ${component} now at ${target_pct}%"
}

cmd_complete_rollout() {
    local component="$1"

    log_info "Completing rollout for: ${component} (100%)"

    if ! check_health "${component}"; then
        log_error "Health checks failed. Refusing to complete rollout."
        exit 1
    fi

    if ! cmd_validate_performance "${component}"; then
        log_error "Performance validation failed. Refusing to complete rollout."
        log_warn "Run rollback: ./scripts/rollback.sh rollback ${component}"
        exit 1
    fi

    set_flag "${component}" "true" "${PHASE_4_PCT}"
    log_success "Rollout complete: ${component} at 100%"
    log_warn "Legacy path will remain available for 24 hours for emergency rollback."
    log_warn "After 24 hours of stable operation, legacy code can be removed."
}

cmd_rollback() {
    local component="$1"

    log_warn "ROLLING BACK: ${component} → legacy path (0%)"

    set_flag "${component}" "false" "0" "canary-rollout.sh/rollback"

    log_success "Rollback complete: ${component} is now on the legacy path"
    log_info "All new requests will be routed to the legacy component."
    log_info "In-flight tasks will complete on their current path."
    log_warn "File an incident report and investigate before re-attempting the rollout."
}

cmd_status() {
    local component="$1"

    log_info "Current canary state for: ${component}"
    echo ""
    get_flag_state "${component}"
    echo ""
}

# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

usage() {
    sed -n '/^# Usage:/,/^# Validates:/p' "$0" | head -n -1
    exit 1
}

if [[ $# -lt 2 ]]; then
    usage
fi

COMMAND="$1"
COMPONENT="$2"

case "${COMMAND}" in
    capture-baseline)
        cmd_capture_baseline "${COMPONENT}"
        ;;
    start-canary)
        cmd_start_canary "${COMPONENT}"
        ;;
    increase-traffic)
        if [[ $# -lt 3 ]]; then
            log_error "increase-traffic requires a percentage argument"
            usage
        fi
        cmd_increase_traffic "${COMPONENT}" "$3"
        ;;
    complete-rollout)
        cmd_complete_rollout "${COMPONENT}"
        ;;
    rollback)
        cmd_rollback "${COMPONENT}"
        ;;
    status)
        cmd_status "${COMPONENT}"
        ;;
    validate-performance)
        cmd_validate_performance "${COMPONENT}"
        ;;
    *)
        log_error "Unknown command: ${COMMAND}"
        usage
        ;;
esac
