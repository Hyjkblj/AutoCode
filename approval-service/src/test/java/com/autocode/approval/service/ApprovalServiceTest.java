package com.autocode.approval.service;

import com.autocode.approval.dto.ApprovalDecisionDto;
import com.autocode.approval.dto.ApprovalRequestDto;
import com.autocode.approval.dto.ApprovalResponseDto;
import com.autocode.approval.entity.ApprovalEntity;
import com.autocode.approval.repository.ApprovalRepository;
import com.autocode.protocol.model.ApprovalDecision;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class ApprovalServiceTest {

    @Mock
    private ApprovalRepository approvalRepository;

    @Mock
    private RbacService rbacService;

    @Mock
    private AuditService auditService;

    private ApprovalService approvalService;
    private ObjectMapper objectMapper;

    @BeforeEach
    void setUp() {
        objectMapper = new ObjectMapper();
        approvalService = new ApprovalService(approvalRepository, rbacService, auditService, objectMapper);
        
        // Set default timeout values
        ReflectionTestUtils.setField(approvalService, "defaultTimeoutSeconds", 300);
        ReflectionTestUtils.setField(approvalService, "maxTimeoutSeconds", 3600);
    }

    @Test
    void createApproval_Success() {
        // Given
        ApprovalRequestDto request = new ApprovalRequestDto();
        request.setApprovalId("apr_001");
        request.setTaskId("task_001");
        request.setAction("app.generate");
        request.setTool("command.exec");
        request.setCommand("mvn test");
        request.setRiskScore(0.5);

        ApprovalEntity savedEntity = new ApprovalEntity();
        savedEntity.setApprovalId("apr_001");
        savedEntity.setTaskId("task_001");
        savedEntity.setDecision(ApprovalDecision.PENDING);

        when(approvalRepository.existsById("apr_001")).thenReturn(false);
        when(approvalRepository.save(any(ApprovalEntity.class))).thenReturn(savedEntity);

        // When
        ApprovalResponseDto result = approvalService.createApproval(request);

        // Then
        assertNotNull(result);
        assertEquals("apr_001", result.getApprovalId());
        assertEquals("task_001", result.getTaskId());
        assertEquals(ApprovalDecision.PENDING, result.getDecision());

        verify(approvalRepository).existsById("apr_001");
        verify(approvalRepository).save(any(ApprovalEntity.class));
        verify(auditService).logApprovalCreated(savedEntity);
    }

    @Test
    void createApproval_AlreadyExists() {
        // Given
        ApprovalRequestDto request = new ApprovalRequestDto();
        request.setApprovalId("apr_001");

        when(approvalRepository.existsById("apr_001")).thenReturn(true);

        // When & Then
        assertThrows(IllegalArgumentException.class, () -> approvalService.createApproval(request));
        verify(approvalRepository).existsById("apr_001");
        verify(approvalRepository, never()).save(any());
    }

    @Test
    void submitDecision_Success() {
        // Given
        String approvalId = "apr_001";
        String userId = "user_001";
        
        ApprovalDecisionDto decision = new ApprovalDecisionDto();
        decision.setDecision(ApprovalDecision.APPROVE);
        decision.setMessage("Approved by admin");

        ApprovalEntity entity = new ApprovalEntity();
        entity.setApprovalId(approvalId);
        entity.setTaskId("task_001");
        entity.setDecision(ApprovalDecision.PENDING);

        ApprovalEntity savedEntity = new ApprovalEntity();
        savedEntity.setApprovalId(approvalId);
        savedEntity.setDecision(ApprovalDecision.APPROVE);
        savedEntity.setDecisionMessage("Approved by admin");
        savedEntity.setDecidedBy(userId);

        when(approvalRepository.findById(approvalId)).thenReturn(Optional.of(entity));
        when(rbacService.canApprove(userId, "task_001")).thenReturn(true);
        when(approvalRepository.save(any(ApprovalEntity.class))).thenReturn(savedEntity);

        // When
        ApprovalResponseDto result = approvalService.submitDecision(approvalId, decision, userId);

        // Then
        assertNotNull(result);
        assertEquals(approvalId, result.getApprovalId());
        assertEquals(ApprovalDecision.APPROVE, result.getDecision());
        assertEquals("Approved by admin", result.getDecisionMessage());
        assertEquals(userId, result.getDecidedBy());

        verify(approvalRepository).findById(approvalId);
        verify(rbacService).canApprove(userId, "task_001");
        verify(approvalRepository).save(any(ApprovalEntity.class));
        verify(auditService).logApprovalDecision(savedEntity);
    }

    @Test
    void submitDecision_NotFound() {
        // Given
        String approvalId = "apr_001";
        String userId = "user_001";
        ApprovalDecisionDto decision = new ApprovalDecisionDto();

        when(approvalRepository.findById(approvalId)).thenReturn(Optional.empty());

        // When & Then
        assertThrows(IllegalArgumentException.class, 
                () -> approvalService.submitDecision(approvalId, decision, userId));
        verify(approvalRepository).findById(approvalId);
        verify(rbacService, never()).canApprove(anyString(), anyString());
    }

    @Test
    void submitDecision_AlreadyDecided() {
        // Given
        String approvalId = "apr_001";
        String userId = "user_001";
        ApprovalDecisionDto decision = new ApprovalDecisionDto();

        ApprovalEntity entity = new ApprovalEntity();
        entity.setApprovalId(approvalId);
        entity.setDecision(ApprovalDecision.APPROVE); // Already decided

        when(approvalRepository.findById(approvalId)).thenReturn(Optional.of(entity));

        // When & Then
        assertThrows(IllegalStateException.class, 
                () -> approvalService.submitDecision(approvalId, decision, userId));
        verify(approvalRepository).findById(approvalId);
        verify(rbacService, never()).canApprove(anyString(), anyString());
    }

    @Test
    void submitDecision_AccessDenied() {
        // Given
        String approvalId = "apr_001";
        String userId = "user_001";
        ApprovalDecisionDto decision = new ApprovalDecisionDto();

        ApprovalEntity entity = new ApprovalEntity();
        entity.setApprovalId(approvalId);
        entity.setTaskId("task_001");
        entity.setDecision(ApprovalDecision.PENDING);

        when(approvalRepository.findById(approvalId)).thenReturn(Optional.of(entity));
        when(rbacService.canApprove(userId, "task_001")).thenReturn(false);

        // When & Then
        assertThrows(SecurityException.class, 
                () -> approvalService.submitDecision(approvalId, decision, userId));
        verify(approvalRepository).findById(approvalId);
        verify(rbacService).canApprove(userId, "task_001");
        verify(approvalRepository, never()).save(any());
    }

    @Test
    void getApproval_Success() {
        // Given
        String approvalId = "apr_001";
        ApprovalEntity entity = new ApprovalEntity();
        entity.setApprovalId(approvalId);
        entity.setTaskId("task_001");
        entity.setDecision(ApprovalDecision.PENDING);

        when(approvalRepository.findById(approvalId)).thenReturn(Optional.of(entity));

        // When
        ApprovalResponseDto result = approvalService.getApproval(approvalId);

        // Then
        assertNotNull(result);
        assertEquals(approvalId, result.getApprovalId());
        assertEquals("task_001", result.getTaskId());
        assertEquals(ApprovalDecision.PENDING, result.getDecision());

        verify(approvalRepository).findById(approvalId);
    }

    @Test
    void getApproval_NotFound() {
        // Given
        String approvalId = "apr_001";
        when(approvalRepository.findById(approvalId)).thenReturn(Optional.empty());

        // When & Then
        assertThrows(IllegalArgumentException.class, () -> approvalService.getApproval(approvalId));
        verify(approvalRepository).findById(approvalId);
    }
}