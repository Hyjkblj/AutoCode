# Approval Service

The Approval Service is an independent microservice that manages approval workflows, security gates, and Role-Based Access Control (RBAC) for the AutoCode system.

## Overview

This service is responsible for:
- Managing approval requests for high-risk task operations
- Enforcing RBAC (Role-Based Access Control)
- Maintaining audit trail for approval decisions
- Project membership and permission management

## Architecture

The service follows a layered architecture:
- **Controller Layer**: REST API endpoints for approval operations
- **Service Layer**: Business logic for approvals, RBAC, and audit
- **Repository Layer**: Data access using Spring Data JPA
- **Entity Layer**: JPA entities for database persistence

## Key Components

### Services
- `ApprovalService`: Core approval workflow management
- `RbacService`: Role-based access control enforcement
- `AuditService`: Audit trail logging for compliance

### Entities
- `ApprovalEntity`: Approval requests and decisions
- `UserEntity`: User information
- `UserRoleEntity`: User role assignments
- `ProjectMembershipEntity`: Project membership and roles

### DTOs
- `ApprovalRequestDto`: Create approval request
- `ApprovalResponseDto`: Approval response data
- `ApprovalDecisionDto`: Submit approval decision

## API Endpoints

### Create Approval Request
```
POST /api/v1/approvals
Content-Type: application/json

{
  "approvalId": "apr_001",
  "taskId": "task_001",
  "action": "app.generate",
  "tool": "command.exec",
  "command": "mvn test",
  "riskScore": 0.5
}
```

### Submit Approval Decision
```
POST /api/v1/approvals/{approvalId}/decision
X-User-ID: user_001
Content-Type: application/json

{
  "decision": "APPROVE",
  "message": "Approved by admin"
}
```

### Get Approval
```
GET /api/v1/approvals/{approvalId}
```

### List Approvals
```
GET /api/v1/approvals?taskId=task_001
GET /api/v1/approvals?pendingOnly=true
```

## Configuration

The service can be configured via environment variables:

- `APPROVAL_DB_URL`: Database connection URL
- `APPROVAL_DB_USER`: Database username
- `APPROVAL_DB_PASSWORD`: Database password
- `CONTROL_PLANE_URL`: Control Plane service URL

## Database Schema

The service uses MySQL with the following main tables:
- `approvals`: Approval requests and decisions
- `users`: User information
- `user_roles`: User role assignments
- `project_memberships`: Project membership and roles

## RBAC Model

Users can have approval permissions through:
1. **Global roles**: `admin`, `approver`, `owner`
2. **Project roles**: `admin`, `owner` within specific projects

## Security

- Input validation using Jakarta Bean Validation
- RBAC enforcement for all approval operations
- Comprehensive audit logging
- Secure database connections

## Testing

The service includes comprehensive tests:
- Unit tests for services and repositories
- Integration tests for REST controllers
- Property-based tests for correctness validation

Run tests:
```bash
mvn test
```

## Building and Running

### Build
```bash
mvn clean package
```

### Run locally
```bash
java -jar target/approval-service-0.1.0-SNAPSHOT.jar
```

### Docker
```bash
docker build -t approval-service .
docker run -p 8064:8064 approval-service
```

## Health Check

The service provides health check endpoints:
- `/actuator/health`: Spring Boot health check
- `/api/v1/approvals/health`: Simple health check

## Metrics

Prometheus metrics are exposed at `/actuator/prometheus` for monitoring:
- Request counts and latencies
- Database connection pool metrics
- JVM metrics

## Compliance

The service maintains comprehensive audit trails for:
- Approval creation events
- Approval decision events
- Permission check events
- Security violation events

All audit events are logged with structured data for compliance reporting.

## Requirements Validation

This service validates the following requirements:
- **11.1**: Clear service boundaries for Java microservices decomposition
- **13.2**: RBAC implementation for administrative functions
- **13.3**: Comprehensive audit trail for approval actions