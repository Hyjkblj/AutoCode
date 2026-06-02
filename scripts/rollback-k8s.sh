#!/bin/bash
# AutoCode K8s deployment rollback script
# Usage: ./scripts/rollback-k8s.sh [service-name]
# If no service specified, rolls back all services

set -euo pipefail

NAMESPACE="autocode"

ALL_SERVICES=(
    "control-plane"
    "gateway-service"
    "approval-service"
    "artifact-service"
    "event-service"
    "python-agent"
)

if [[ $# -gt 0 ]]; then
    SERVICES=("$@")
else
    SERVICES=("${ALL_SERVICES[@]}")
fi

echo "========================================="
echo "AutoCode K8s Rollback"
echo "Namespace: $NAMESPACE"
echo "Services:  ${SERVICES[*]}"
echo "Time:      $(date -Iseconds)"
echo "========================================="
echo ""

for svc in "${SERVICES[@]}"; do
    echo "Rolling back $svc..."
    kubectl rollout undo "deployment/$svc" -n "$NAMESPACE"
done

echo ""
echo "Waiting for rollbacks to complete..."
for svc in "${SERVICES[@]}"; do
    kubectl rollout status "deployment/$svc" -n "$NAMESPACE" --timeout=120s
done

echo ""
echo "========================================="
echo "Rollback complete. Verifying health..."
echo "========================================="
echo ""

for svc in "${SERVICES[@]}"; do
    READY=$(kubectl get deployment "$svc" -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
    DESIRED=$(kubectl get deployment "$svc" -n "$NAMESPACE" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")
    if [ "$READY" = "$DESIRED" ] && [ "$READY" != "0" ]; then
        echo "  [OK]   $svc: $READY/$DESIRED replicas ready"
    else
        echo "  [WARN] $svc: $READY/$DESIRED replicas ready"
    fi
done
