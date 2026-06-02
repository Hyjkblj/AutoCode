#!/usr/bin/env bash
# =============================================================================
# rollback.sh — Rollback procedures for Backend Upgrade 2.0
#
# Usage:
#   ./scripts/rollback.sh <command> <component>
#
# Commands:
#   rollback       <component>   Immediately disable a feature flag (legacy path)
#   auto-rollback  <component>   Automated rollback triggered by Alertmanager
#   phase-rollback <component> <target_pct>  Roll back to a specific phase percentage
#   health-check   <component>   Validate system health after rollback
#   status         <component>   Show current flag state
#
# Components:
#   langgraph_engine, new_backend_generator, spring_cloud_gateway,
#   artifact_microservice, event_microservice, approval_microservice,
#   new_validation_gate, distributed_lock_v2
#
# Environment variables:
#   REDIS_HOST          Redis host (default: localhost)
#   REDIS_PORT          Redis port (default: 6379)
#   REDIS_PASSWORD      Redis password (optional)
#   ALERTMANAGER_URL    Alertmanager URL for notifications (default: http://localhost:9093)
#   SLACK_WEBHOOK_URL   Slack webhook for rollback notifications (optional)
#   ROLLBACK_LOG_DIR    Directory for rollback logs (default: /tmp/rollback-logs)
#
# Validates: Requirements 11.3, 11.5, 11.7
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"
REDIS_PASSWORD="${REDIS_PASSWORD:-}"
ALERTMANAGER_URL="${ALERTMANAGER_URL:-http://localhost:9093}"
SLACK_WEBHOOK_URL="${SLACK_WEBHOOK_URL:-}"
ROLLBACK_LOG_DIR="${ROLLBACK_LOG_DIR:-/tmp/rollback-logs}"

# Health check settings
HEALTH_CHECK_RETRIES=5
HEALTH_CHECK_INTERVAL=10  # seconds

# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info()    { echo -e "${BLUE}[INFO]${NC}     $*"; }
log_success() { echo -e "${GREEN}[OK]${NC}       $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC}     $*"; }
log_error()   { echo -e "${RED}[ERROR]${NC}    $*" >&2; }
log_rollback(){ echo -e "${CYAN}[ROLLBACK]${NC} $*"; }

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

redis_set() { redis_cmd SET "$1" "$2" > /dev/null; }
redis_get()  { redis_cmd GET "$1"; }

flag_key_enabled()    { echo "feature_flag:${1}:enabled"; }
flag_key_canary()     { echo "feature_flag:${1}:canary_percentage"; }
flag_key_updated_at() { echo "feature_flag:${1}:updated_at"; }
flag_key_updated_by() { echo "feature_flag:${1}:updated_by"; }

disable_flag() {
    local component="$1"
    local updated_by="${2:-rollback.sh}"
    local now
    now=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    redis_set "$(flag_key_enabled    "${component}")" "false"
    redis_set "$(flag_key_canary     "${component}")" "0"
    redis_set "$(flag_key_updated_at "${component}")" "${now}"
    redis_set "$(flag_key_updated_by "${component}")" "${updated_by}"
}

set_canary_pct() {
    local component="$1"
    local pct="$2"
    local updated_by="${3:-rollback.sh}"
    local now
    now=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    redis_set "$(flag_key_canary     "${component}")" "${pct}"
    redis_set "$(flag_key_updated_at "${component}")" "${now}"
    redis_set "$(flag_key_updated_by "${component}")" "${updated_by}"
}

get_current_pct() {
    local component="$1"
    redis_get "$(flag_key_canary "${component}")" || echo "0"
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

init_rollback_log() {
    local component="$1"
    mkdir -p "${ROLLBACK_LOG_DIR}"
    local log_file="${ROLLBACK_LOG_DIR}/${component}-$(date -u +"%Y%m%dT%H%M%SZ").log"
    echo "${log_file}"
}

write_rollback_log() {
    local log_file="$1"
    local component="$2"
    local trigger="$3"
    local from_pct="$4"
    local to_pct="$5"

    cat >> "${log_file}" <<EOF
{
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "component": "${component}",
  "trigger": "${trigger}",
  "from_canary_percentage": ${from_pct},
  "to_canary_percentage": ${to_pct},
  "host": "$(hostname)",
  "operator": "${USER:-unknown}"
}
EOF
    log_info "Rollback logged to: ${log_file}"
}

# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

notify_slack() {
    local component="$1"
    local trigger="$2"
    local from_pct="$3"

    if [[ -z "${SLACK_WEBHOOK_URL}" ]]; then
        return 0
    fi

    local payload
    payload=$(cat <<EOF
{
  "text": ":rotating_light: *Rollback triggered* for \`${component}\`",
  "attachments": [{
    "color": "danger",
    "fields": [
      {"title": "Component", "value": "${component}", "short": true},
      {"title": "Trigger",   "value": "${trigger}",   "short": true},
      {"title": "From",      "value": "${from_pct}%", "short": true},
      {"title": "To",        "value": "0% (legacy)",  "short": true},
      {"title": "Time",      "value": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")", "short": false}
    ]
  }]
}
EOF
)

    curl -sf -X POST -H 'Content-type: application/json' \
        --data "${payload}" "${SLACK_WEBHOOK_URL}" > /dev/null 2>&1 || true
}

notify_alertmanager() {
    local component="$1"
    local trigger="$2"

    # Resolve the rollback alert in Alertmanager so it doesn't keep firing
    local payload
    payload=$(cat <<EOF
[{
  "labels": {
    "alertname": "CanaryRollback",
    "component": "${component}",
    "trigger": "${trigger}"
  },
  "endsAt": "$(date -u -d '+5 minutes' +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date -u +"%Y-%m-%dT%H:%M:%SZ")"
}]
EOF
)

    curl -sf -X POST \
        -H 'Content-type: application/json' \
        --data "${payload}" \
        "${ALERTMANAGER_URL}/api/v1/alerts" > /dev/null 2>&1 || true
}

# ---------------------------------------------------------------------------
# Health validation
# ---------------------------------------------------------------------------

validate_health_after_rollback() {
    local component="$1"
    local attempt=0

    log_info "Validating system health after rollback for: ${component}"

    while [[ ${attempt} -lt ${HEALTH_CHECK_RETRIES} ]]; do
        attempt=$(( attempt + 1 ))
        local all_ok=true

        # Control Plane
        if curl -sf "http://localhost:8058/actuator/health" > /dev/null 2>&1; then
            log_success "Control Plane: healthy (attempt ${attempt})"
        else
            log_warn "Control Plane: unhealthy (attempt ${attempt}/${HEALTH_CHECK_RETRIES})"
            all_ok=false
        fi

        # Redis
        if redis_cmd PING | grep -q "PONG"; then
            log_success "Redis: healthy"
        else
            log_warn "Redis: unhealthy (attempt ${attempt}/${HEALTH_CHECK_RETRIES})"
            all_ok=false
        fi

        # Java Sandbox
        if curl -sf "http://localhost:18080/sandbox/health" > /dev/null 2>&1; then
            log_success "Java Sandbox: healthy"
        else
            log_warn "Java Sandbox: unhealthy (attempt ${attempt}/${HEALTH_CHECK_RETRIES})"
            # Non-fatal — sandbox may not be required for all components
        fi

        if [[ "${all_ok}" == "true" ]]; then
            log_success "All health checks passed after rollback"
            return 0
        fi

        if [[ ${attempt} -lt ${HEALTH_CHECK_RETRIES} ]]; then
            log_info "Retrying health checks in ${HEALTH_CHECK_INTERVAL}s..."
            sleep "${HEALTH_CHECK_INTERVAL}"
        fi
    done

    log_error "Health checks still failing after rollback. Manual intervention required."
    return 1
}

# ---------------------------------------------------------------------------
# Rollback commands
# ---------------------------------------------------------------------------

cmd_rollback() {
    local component="$1"
    local trigger="${2:-manual}"

    log_rollback "=========================================="
    log_rollback "ROLLBACK INITIATED"
    log_rollback "Component: ${component}"
    log_rollback "Trigger:   ${trigger}"
    log_rollback "Time:      $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    log_rollback "=========================================="

    local from_pct
    from_pct=$(get_current_pct "${component}")

    local log_file
    log_file=$(init_rollback_log "${component}")

    # Disable the flag immediately — takes effect on next Redis read
    disable_flag "${component}" "rollback.sh/${trigger}"

    log_rollback "Feature flag disabled: ${component} → legacy path (0%)"
    log_rollback "Effect is immediate — next task dispatch will use legacy path."

    # Log the rollback event
    write_rollback_log "${log_file}" "${component}" "${trigger}" "${from_pct}" "0"

    # Send notifications
    notify_slack "${component}" "${trigger}" "${from_pct}"
    notify_alertmanager "${component}" "${trigger}"

    # Validate health
    if validate_health_after_rollback "${component}"; then
        log_success "Rollback complete and system is healthy."
    else
        log_error "Rollback complete but system health checks are failing."
        log_error "Escalate immediately — manual intervention may be required."
        exit 1
    fi

    echo ""
    log_warn "Next steps:"
    log_warn "  1. Capture error logs from the canary period."
    log_warn "  2. File an incident report: trigger=${trigger}, component=${component}."
    log_warn "  3. Conduct root cause analysis before re-attempting the rollout."
    log_warn "  4. Update the rollout plan with lessons learned."
}

cmd_auto_rollback() {
    local component="$1"
    log_warn "Automated rollback triggered by monitoring system for: ${component}"
    cmd_rollback "${component}" "automated-monitoring"
}

cmd_phase_rollback() {
    local component="$1"
    local target_pct="$2"

    if ! [[ "${target_pct}" =~ ^[0-9]+$ ]] || [[ "${target_pct}" -gt 100 ]]; then
        log_error "Invalid percentage: ${target_pct}. Must be 0–100."
        exit 1
    fi

    local from_pct
    from_pct=$(get_current_pct "${component}")

    log_rollback "Phase rollback: ${component} from ${from_pct}% → ${target_pct}%"

    if [[ "${target_pct}" -eq 0 ]]; then
        cmd_rollback "${component}" "phase-rollback-to-0"
        return
    fi

    local log_file
    log_file=$(init_rollback_log "${component}")

    set_canary_pct "${component}" "${target_pct}" "rollback.sh/phase-rollback"
    write_rollback_log "${log_file}" "${component}" "phase-rollback" "${from_pct}" "${target_pct}"

    log_success "Phase rollback complete: ${component} is now at ${target_pct}%"
    log_info "Monitor for 15 minutes before deciding to roll back further."

    notify_slack "${component}" "phase-rollback-to-${target_pct}pct" "${from_pct}"
}

cmd_health_check() {
    local component="$1"
    validate_health_after_rollback "${component}"
}

cmd_status() {
    local component="$1"
    local enabled canary_pct updated_at updated_by

    enabled=$(redis_get "$(flag_key_enabled    "${component}")" || echo "<not set>")
    canary_pct=$(redis_get "$(flag_key_canary  "${component}")" || echo "<not set>")
    updated_at=$(redis_get "$(flag_key_updated_at "${component}")" || echo "<not set>")
    updated_by=$(redis_get "$(flag_key_updated_by "${component}")" || echo "<not set>")

    echo ""
    log_info "Feature flag state for: ${component}"
    echo "  enabled:           ${enabled}"
    echo "  canary_percentage: ${canary_pct}"
    echo "  updated_at:        ${updated_at}"
    echo "  updated_by:        ${updated_by}"
    echo ""
}

# ---------------------------------------------------------------------------
# Phase-specific rollback procedures (documented)
# ---------------------------------------------------------------------------

print_phase_procedures() {
    cat <<'EOF'

Phase-Specific Rollback Procedures
===================================

Phase 1 → Phase 0 (5% → 0%)
  ./scripts/rollback.sh rollback <component>
  - Disables the feature flag immediately.
  - All traffic returns to the legacy path.
  - Capture error logs from the canary period.

Phase 2 → Phase 1 (25% → 5%)
  ./scripts/rollback.sh phase-rollback <component> 5
  - Reduces canary traffic to 5%.
  - Monitor for 15 minutes; if issues persist, roll back to 0%.

Phase 3 → Phase 2 (50% → 25%)
  ./scripts/rollback.sh phase-rollback <component> 25
  - Reduces canary traffic to 25%.
  - Monitor for 30 minutes; if issues persist, reduce further.

Phase 4 → Phase 3 (100% → 50%)
  ./scripts/rollback.sh phase-rollback <component> 50
  - Reduces traffic to 50% if legacy code is still available.
  - If legacy code was removed, a hotfix deployment is required — escalate.

Emergency (any phase → 0%)
  ./scripts/rollback.sh rollback <component>
  - Immediately disables the feature flag.
  - Takes effect on the next Redis read (< 100ms).
  - No service restart required.

EOF
}

# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

usage() {
    echo "Usage: $0 <command> <component> [options]"
    echo ""
    echo "Commands:"
    echo "  rollback       <component>              Immediately disable flag (legacy path)"
    echo "  auto-rollback  <component>              Automated rollback (called by Alertmanager)"
    echo "  phase-rollback <component> <target_pct> Roll back to a specific phase percentage"
    echo "  health-check   <component>              Validate health after rollback"
    echo "  status         <component>              Show current flag state"
    echo "  procedures                              Print phase-specific rollback procedures"
    exit 1
}

if [[ $# -lt 1 ]]; then
    usage
fi

COMMAND="$1"

case "${COMMAND}" in
    rollback)
        [[ $# -lt 2 ]] && usage
        cmd_rollback "$2"
        ;;
    auto-rollback)
        [[ $# -lt 2 ]] && usage
        cmd_auto_rollback "$2"
        ;;
    phase-rollback)
        [[ $# -lt 3 ]] && { log_error "phase-rollback requires component and target_pct"; usage; }
        cmd_phase_rollback "$2" "$3"
        ;;
    health-check)
        [[ $# -lt 2 ]] && usage
        cmd_health_check "$2"
        ;;
    status)
        [[ $# -lt 2 ]] && usage
        cmd_status "$2"
        ;;
    procedures)
        print_phase_procedures
        ;;
    *)
        log_error "Unknown command: ${COMMAND}"
        usage
        ;;
esac
