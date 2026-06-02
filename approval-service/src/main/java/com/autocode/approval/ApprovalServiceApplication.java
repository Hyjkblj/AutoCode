package com.autocode.approval;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * Approval Service - Manages approval workflows, security gates, and RBAC.
 * 
 * <p>This microservice is responsible for:
 * <ul>
 *   <li>Managing approval requests for high-risk task operations</li>
 *   <li>Enforcing RBAC (Role-Based Access Control)</li>
 *   <li>Maintaining audit trail for approval decisions</li>
 *   <li>Project membership and permission management</li>
 * </ul>
 * 
 * <p>Validates: Requirements 11.1 (Clear Service Boundaries), 13.2 (RBAC), 13.3 (Audit Trail)
 */
@SpringBootApplication
public class ApprovalServiceApplication {

    public static void main(String[] args) {
        SpringApplication.run(ApprovalServiceApplication.class, args);
    }
}
