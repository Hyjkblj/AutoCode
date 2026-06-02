package com.autocode.approval.controller;

import com.autocode.approval.dto.ApprovalDecisionDto;
import com.autocode.approval.dto.ApprovalRequestDto;
import com.autocode.approval.dto.ApprovalResponseDto;
import com.autocode.approval.service.ApprovalService;
import com.autocode.protocol.model.ApprovalDecision;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.time.Instant;
import java.util.Arrays;
import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@WebMvcTest(ApprovalController.class)
class ApprovalControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private ApprovalService approvalService;

    @Autowired
    private ObjectMapper objectMapper;

    @Test
    void createApproval_Success() throws Exception {
        // Given
        ApprovalRequestDto request = new ApprovalRequestDto();
        request.setApprovalId("apr_001");
        request.setTaskId("task_001");
        request.setAction("app.generate");
        request.setTool("command.exec");
        request.setCommand("mvn test");
        request.setRiskScore(0.5);

        ApprovalResponseDto response = new ApprovalResponseDto();
        response.setApprovalId("apr_001");
        response.setTaskId("task_001");
        response.setDecision(ApprovalDecision.PENDING);
        response.setCreatedAt(Instant.now());

        when(approvalService.createApproval(any(ApprovalRequestDto.class))).thenReturn(response);

        // When & Then
        mockMvc.perform(post("/api/v1/approvals")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.approvalId").value("apr_001"))
                .andExpect(jsonPath("$.taskId").value("task_001"))
                .andExpect(jsonPath("$.decision").value("PENDING"));
    }

    @Test
    void createApproval_InvalidRequest() throws Exception {
        // Given
        ApprovalRequestDto request = new ApprovalRequestDto();
        request.setApprovalId("apr_001");
        // Missing required fields

        when(approvalService.createApproval(any(ApprovalRequestDto.class)))
                .thenThrow(new IllegalArgumentException("Invalid request"));

        // When & Then
        mockMvc.perform(post("/api/v1/approvals")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest());
    }

    @Test
    void submitDecision_Success() throws Exception {
        // Given
        String approvalId = "apr_001";
        String userId = "user_001";
        
        ApprovalDecisionDto decision = new ApprovalDecisionDto();
        decision.setDecision(ApprovalDecision.APPROVE);
        decision.setMessage("Approved by admin");

        ApprovalResponseDto response = new ApprovalResponseDto();
        response.setApprovalId(approvalId);
        response.setDecision(ApprovalDecision.APPROVE);
        response.setDecisionMessage("Approved by admin");
        response.setDecidedBy(userId);
        response.setDecidedAt(Instant.now());

        when(approvalService.submitDecision(eq(approvalId), any(ApprovalDecisionDto.class), eq(userId)))
                .thenReturn(response);

        // When & Then
        mockMvc.perform(post("/api/v1/approvals/{approvalId}/decision", approvalId)
                .header("X-User-ID", userId)
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(decision)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.approvalId").value(approvalId))
                .andExpect(jsonPath("$.decision").value("APPROVE"))
                .andExpect(jsonPath("$.decisionMessage").value("Approved by admin"))
                .andExpect(jsonPath("$.decidedBy").value(userId));
    }

    @Test
    void submitDecision_MissingUserId() throws Exception {
        // Given
        String approvalId = "apr_001";
        ApprovalDecisionDto decision = new ApprovalDecisionDto();
        decision.setDecision(ApprovalDecision.APPROVE);

        // When & Then
        mockMvc.perform(post("/api/v1/approvals/{approvalId}/decision", approvalId)
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(decision)))
                .andExpect(status().isBadRequest());
    }

    @Test
    void submitDecision_AccessDenied() throws Exception {
        // Given
        String approvalId = "apr_001";
        String userId = "user_001";
        ApprovalDecisionDto decision = new ApprovalDecisionDto();
        decision.setDecision(ApprovalDecision.APPROVE);

        when(approvalService.submitDecision(eq(approvalId), any(ApprovalDecisionDto.class), eq(userId)))
                .thenThrow(new SecurityException("Access denied"));

        // When & Then
        mockMvc.perform(post("/api/v1/approvals/{approvalId}/decision", approvalId)
                .header("X-User-ID", userId)
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(decision)))
                .andExpect(status().isForbidden());
    }

    @Test
    void submitDecision_AlreadyDecided() throws Exception {
        // Given
        String approvalId = "apr_001";
        String userId = "user_001";
        ApprovalDecisionDto decision = new ApprovalDecisionDto();
        decision.setDecision(ApprovalDecision.APPROVE);

        when(approvalService.submitDecision(eq(approvalId), any(ApprovalDecisionDto.class), eq(userId)))
                .thenThrow(new IllegalStateException("Already decided"));

        // When & Then
        mockMvc.perform(post("/api/v1/approvals/{approvalId}/decision", approvalId)
                .header("X-User-ID", userId)
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(decision)))
                .andExpect(status().isConflict());
    }

    @Test
    void getApproval_Success() throws Exception {
        // Given
        String approvalId = "apr_001";
        ApprovalResponseDto response = new ApprovalResponseDto();
        response.setApprovalId(approvalId);
        response.setTaskId("task_001");
        response.setDecision(ApprovalDecision.PENDING);

        when(approvalService.getApproval(approvalId)).thenReturn(response);

        // When & Then
        mockMvc.perform(get("/api/v1/approvals/{approvalId}", approvalId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.approvalId").value(approvalId))
                .andExpect(jsonPath("$.taskId").value("task_001"))
                .andExpect(jsonPath("$.decision").value("PENDING"));
    }

    @Test
    void getApproval_NotFound() throws Exception {
        // Given
        String approvalId = "apr_001";
        when(approvalService.getApproval(approvalId))
                .thenThrow(new IllegalArgumentException("Approval not found"));

        // When & Then
        mockMvc.perform(get("/api/v1/approvals/{approvalId}", approvalId))
                .andExpect(status().isNotFound());
    }

    @Test
    void getApprovals_PendingOnly() throws Exception {
        // Given
        ApprovalResponseDto approval1 = new ApprovalResponseDto();
        approval1.setApprovalId("apr_001");
        approval1.setDecision(ApprovalDecision.PENDING);

        ApprovalResponseDto approval2 = new ApprovalResponseDto();
        approval2.setApprovalId("apr_002");
        approval2.setDecision(ApprovalDecision.PENDING);

        List<ApprovalResponseDto> response = Arrays.asList(approval1, approval2);
        when(approvalService.getPendingApprovals()).thenReturn(response);

        // When & Then
        mockMvc.perform(get("/api/v1/approvals")
                .param("pendingOnly", "true"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(2))
                .andExpect(jsonPath("$[0].approvalId").value("apr_001"))
                .andExpect(jsonPath("$[1].approvalId").value("apr_002"));
    }

    @Test
    void getApprovals_ByTaskId() throws Exception {
        // Given
        String taskId = "task_001";
        ApprovalResponseDto approval = new ApprovalResponseDto();
        approval.setApprovalId("apr_001");
        approval.setTaskId(taskId);

        List<ApprovalResponseDto> response = Arrays.asList(approval);
        when(approvalService.getApprovalsByTask(taskId)).thenReturn(response);

        // When & Then
        mockMvc.perform(get("/api/v1/approvals")
                .param("taskId", taskId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(1))
                .andExpect(jsonPath("$[0].approvalId").value("apr_001"))
                .andExpect(jsonPath("$[0].taskId").value(taskId));
    }

    @Test
    void health_Success() throws Exception {
        mockMvc.perform(get("/api/v1/approvals/health"))
                .andExpect(status().isOk())
                .andExpect(content().string("OK"));
    }
}