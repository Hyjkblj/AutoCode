package com.autocode.approval.controller;

import com.autocode.approval.dto.ApprovalDecisionDto;
import com.autocode.approval.dto.ApprovalRequestDto;
import com.autocode.approval.dto.ApprovalResponseDto;
import com.autocode.approval.service.ApprovalService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import jakarta.validation.Valid;
import java.util.List;

/**
 * REST controller for approval operations.
 * 
 * <p>Validates: Requirements 11.1 (Clear Service Boundaries)
 */
@RestController
@RequestMapping("/api/v1/approvals")
public class ApprovalController {

    private static final Logger logger = LoggerFactory.getLogger(ApprovalController.class);

    private final ApprovalService approvalService;

    public ApprovalController(ApprovalService approvalService) {
        this.approvalService = approvalService;
    }

    /**
     * Create a new approval request.
     */
    @PostMapping
    public ResponseEntity<ApprovalResponseDto> createApproval(@Valid @RequestBody ApprovalRequestDto request) {
        try {
            ApprovalResponseDto response = approvalService.createApproval(request);
            return ResponseEntity.status(HttpStatus.CREATED).body(response);
        } catch (IllegalArgumentException e) {
            logger.error("Invalid approval request: {}", e.getMessage());
            return ResponseEntity.badRequest().build();
        } catch (Exception e) {
            logger.error("Failed to create approval", e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).build();
        }
    }

    /**
     * Submit a decision for an approval request.
     */
    @PostMapping("/{approvalId}/decision")
    public ResponseEntity<ApprovalResponseDto> submitDecision(
            @PathVariable String approvalId,
            @Valid @RequestBody ApprovalDecisionDto decision,
            @RequestHeader(value = "X-User-ID", required = false) String userId) {
        try {
            if (userId == null || userId.trim().isEmpty()) {
                return ResponseEntity.badRequest().build();
            }
            
            ApprovalResponseDto response = approvalService.submitDecision(approvalId, decision, userId);
            return ResponseEntity.ok(response);
        } catch (IllegalArgumentException e) {
            logger.error("Invalid approval decision: {}", e.getMessage());
            return ResponseEntity.badRequest().build();
        } catch (IllegalStateException e) {
            logger.error("Invalid approval state: {}", e.getMessage());
            return ResponseEntity.status(HttpStatus.CONFLICT).build();
        } catch (SecurityException e) {
            logger.error("Access denied: {}", e.getMessage());
            return ResponseEntity.status(HttpStatus.FORBIDDEN).build();
        } catch (Exception e) {
            logger.error("Failed to submit approval decision", e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).build();
        }
    }

    /**
     * Get approval by ID.
     */
    @GetMapping("/{approvalId}")
    public ResponseEntity<ApprovalResponseDto> getApproval(@PathVariable String approvalId) {
        try {
            ApprovalResponseDto response = approvalService.getApproval(approvalId);
            return ResponseEntity.ok(response);
        } catch (IllegalArgumentException e) {
            logger.error("Approval not found: {}", e.getMessage());
            return ResponseEntity.notFound().build();
        } catch (Exception e) {
            logger.error("Failed to get approval", e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).build();
        }
    }

    /**
     * Get all approvals for a task.
     */
    @GetMapping
    public ResponseEntity<List<ApprovalResponseDto>> getApprovals(
            @RequestParam(required = false) String taskId,
            @RequestParam(required = false, defaultValue = "false") boolean pendingOnly) {
        try {
            List<ApprovalResponseDto> response;
            if (pendingOnly) {
                response = approvalService.getPendingApprovals();
            } else if (taskId != null) {
                response = approvalService.getApprovalsByTask(taskId);
            } else {
                response = approvalService.getPendingApprovals(); // Default to pending
            }
            return ResponseEntity.ok(response);
        } catch (Exception e) {
            logger.error("Failed to get approvals", e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).build();
        }
    }

    /**
     * Health check endpoint.
     */
    @GetMapping("/health")
    public ResponseEntity<String> health() {
        return ResponseEntity.ok("OK");
    }
}