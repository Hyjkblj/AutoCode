package com.autocode.approval.service;

import com.autocode.approval.entity.ApprovalEntity;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

/**
 * Service for maintaining audit trail of approval operations.
 * 
 * <p>Validates: Requirements 13.3 (Audit Trail Completeness)
 */
@Service
public class AuditService {

    private static final Logger logger = LoggerFactory.getLogger(AuditService.class);

    /**
     * Log approval creation event.
     */
    public void logApprovalCreated(ApprovalEntity approval) {
        logger.info("AUDIT: Approval created - approvalId={}, taskId={}, action={}, tool={}, riskScore={}, requester=system", 
                approval.getApprovalId(), 
                approval.getTaskId(), 
                approval.getAction(), 
                approval.getTool(), 
                approval.getRiskScore());
    }

    /**
     * Log approval decision event.
     */
    public void logApprovalDecision(ApprovalEntity approval) {
        logger.info("AUDIT: Approval decision - approvalId={}, taskId={}, decision={}, decidedBy={}, decidedAt={}", 
                approval.getApprovalId(), 
                approval.getTaskId(), 
                approval.getDecision(), 
                approval.getDecidedBy(), 
                approval.getDecidedAt());
    }

    /**
     * Log RBAC permission check.
     */
    public void logPermissionCheck(String userId, String taskId, boolean granted) {
        logger.info("AUDIT: Permission check - userId={}, taskId={}, granted={}", userId, taskId, granted);
    }

    /**
     * Log security violation.
     */
    public void logSecurityViolation(String userId, String approvalId, String reason) {
        logger.warn("AUDIT: Security violation - userId={}, approvalId={}, reason={}", userId, approvalId, reason);
    }
}