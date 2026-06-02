package com.autocode.approval.service;

import com.autocode.approval.dto.ApprovalDecisionDto;
import com.autocode.approval.dto.ApprovalRequestDto;
import com.autocode.approval.dto.ApprovalResponseDto;
import com.autocode.approval.entity.ApprovalEntity;
import com.autocode.approval.repository.ApprovalRepository;
import com.autocode.protocol.model.ApprovalContext;
import com.autocode.protocol.model.ApprovalDecision;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.List;
import java.util.stream.Collectors;

/**
 * Service for managing approval workflows and security gates.
 * 
 * <p>Validates: Requirements 13.2 (RBAC), 13.3 (Audit Trail)
 */
@Service
public class ApprovalService {

    private static final Logger logger = LoggerFactory.getLogger(ApprovalService.class);

    private final ApprovalRepository approvalRepository;
    private final RbacService rbacService;
    private final AuditService auditService;
    private final ObjectMapper objectMapper;

    @Value("${approval.default-timeout-seconds:300}")
    private int defaultTimeoutSeconds;

    @Value("${approval.max-timeout-seconds:3600}")
    private int maxTimeoutSeconds;

    public ApprovalService(
            ApprovalRepository approvalRepository,
            RbacService rbacService,
            AuditService auditService,
            ObjectMapper objectMapper) {
        this.approvalRepository = approvalRepository;
        this.rbacService = rbacService;
        this.auditService = auditService;
        this.objectMapper = objectMapper;
    }

    /**
     * Create a new approval request.
     */
    @Transactional
    public ApprovalResponseDto createApproval(ApprovalRequestDto request) {
        logger.info("Creating approval request: approvalId={}, taskId={}", 
                request.getApprovalId(), request.getTaskId());

        // Check if approval already exists
        if (approvalRepository.existsById(request.getApprovalId())) {
            throw new IllegalArgumentException("Approval with ID " + request.getApprovalId() + " already exists");
        }

        // Validate timeout
        int timeoutSeconds = request.getTimeoutSeconds() != null 
                ? request.getTimeoutSeconds() 
                : defaultTimeoutSeconds;
        if (timeoutSeconds > maxTimeoutSeconds) {
            timeoutSeconds = maxTimeoutSeconds;
        }

        // Create entity
        ApprovalEntity entity = new ApprovalEntity();
        entity.setApprovalId(request.getApprovalId());
        entity.setTaskId(request.getTaskId());
        entity.setTraceId(request.getTraceId());
        entity.setRunId(request.getRunId());
        entity.setAction(request.getAction());
        entity.setTool(request.getTool());
        entity.setCommand(request.getCommand());
        entity.setWorkspaceRef(request.getWorkspaceRef());
        entity.setReason(request.getReason());
        entity.setRiskScore(request.getRiskScore());
        entity.setTimeoutSeconds(timeoutSeconds);
        entity.setDecision(ApprovalDecision.PENDING);

        // Serialize context and policies
        try {
            if (request.getContext() != null) {
                entity.setContextJson(objectMapper.writeValueAsString(request.getContext()));
            }
            if (request.getRequiredPolicies() != null && !request.getRequiredPolicies().isEmpty()) {
                entity.setRequiredPolicies(objectMapper.writeValueAsString(request.getRequiredPolicies()));
            }
        } catch (JsonProcessingException e) {
            logger.error("Failed to serialize approval context or policies", e);
            throw new RuntimeException("Failed to serialize approval data", e);
        }

        // Save entity
        ApprovalEntity saved = approvalRepository.save(entity);

        // Audit trail
        auditService.logApprovalCreated(saved);

        logger.info("Approval request created: approvalId={}", saved.getApprovalId());
        return toDto(saved);
    }

    /**
     * Submit a decision for an approval request.
     */
    @Transactional
    public ApprovalResponseDto submitDecision(String approvalId, ApprovalDecisionDto decision, String userId) {
        logger.info("Submitting decision for approval: approvalId={}, decision={}, userId={}", 
                approvalId, decision.getDecision(), userId);

        // Find approval
        ApprovalEntity entity = approvalRepository.findById(approvalId)
                .orElseThrow(() -> new IllegalArgumentException("Approval not found: " + approvalId));

        // Check if already decided
        if (entity.getDecision() != ApprovalDecision.PENDING) {
            throw new IllegalStateException("Approval already decided: " + approvalId);
        }

        // Check RBAC permissions
        if (!rbacService.canApprove(userId, entity.getTaskId())) {
            throw new SecurityException("User does not have permission to approve: " + userId);
        }

        // Update entity
        entity.setDecision(decision.getDecision());
        entity.setDecisionMessage(decision.getMessage());
        entity.setDecidedBy(decision.getDecidedBy() != null ? decision.getDecidedBy() : userId);
        entity.setDecidedAt(Instant.now());

        // Save entity
        ApprovalEntity saved = approvalRepository.save(entity);

        // Audit trail
        auditService.logApprovalDecision(saved);

        logger.info("Approval decision submitted: approvalId={}, decision={}", 
                saved.getApprovalId(), saved.getDecision());
        return toDto(saved);
    }

    /**
     * Get approval by ID.
     */
    public ApprovalResponseDto getApproval(String approvalId) {
        ApprovalEntity entity = approvalRepository.findById(approvalId)
                .orElseThrow(() -> new IllegalArgumentException("Approval not found: " + approvalId));
        return toDto(entity);
    }

    /**
     * Get all approvals for a task.
     */
    public List<ApprovalResponseDto> getApprovalsByTask(String taskId) {
        List<ApprovalEntity> entities = approvalRepository.findByTaskIdOrderByCreatedAtDesc(taskId);
        return entities.stream()
                .map(this::toDto)
                .collect(Collectors.toList());
    }

    /**
     * Get pending approvals.
     */
    public List<ApprovalResponseDto> getPendingApprovals() {
        List<ApprovalEntity> entities = approvalRepository.findByDecisionOrderByCreatedAtDesc(ApprovalDecision.PENDING);
        return entities.stream()
                .map(this::toDto)
                .collect(Collectors.toList());
    }

    /**
     * Convert entity to DTO.
     */
    private ApprovalResponseDto toDto(ApprovalEntity entity) {
        ApprovalResponseDto dto = new ApprovalResponseDto();
        dto.setApprovalId(entity.getApprovalId());
        dto.setTaskId(entity.getTaskId());
        dto.setTraceId(entity.getTraceId());
        dto.setRunId(entity.getRunId());
        dto.setAction(entity.getAction());
        dto.setTool(entity.getTool());
        dto.setCommand(entity.getCommand());
        dto.setWorkspaceRef(entity.getWorkspaceRef());
        dto.setReason(entity.getReason());
        dto.setRiskScore(entity.getRiskScore());
        dto.setDecision(entity.getDecision());
        dto.setDecisionMessage(entity.getDecisionMessage());
        dto.setDecidedBy(entity.getDecidedBy());
        dto.setDecidedAt(entity.getDecidedAt());
        dto.setTimeoutSeconds(entity.getTimeoutSeconds());
        dto.setCreatedAt(entity.getCreatedAt());
        dto.setUpdatedAt(entity.getUpdatedAt());

        // Deserialize context and policies
        try {
            if (entity.getContextJson() != null) {
                dto.setContext(objectMapper.readValue(entity.getContextJson(), ApprovalContext.class));
            }
            if (entity.getRequiredPolicies() != null) {
                dto.setRequiredPolicies(objectMapper.readValue(entity.getRequiredPolicies(), 
                        objectMapper.getTypeFactory().constructCollectionType(List.class, String.class)));
            }
        } catch (JsonProcessingException e) {
            logger.error("Failed to deserialize approval context or policies", e);
        }

        return dto;
    }
}
