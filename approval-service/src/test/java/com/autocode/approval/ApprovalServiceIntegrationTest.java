package com.autocode.approval;

import com.autocode.approval.dto.ApprovalDecisionDto;
import com.autocode.approval.dto.ApprovalRequestDto;
import com.autocode.approval.dto.ApprovalResponseDto;
import com.autocode.approval.entity.UserRoleEntity;
import com.autocode.approval.repository.UserRoleRepository;
import com.autocode.protocol.model.ApprovalDecision;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.context.WebApplicationContext;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@ActiveProfiles("test")
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.ANY)
@Transactional
class ApprovalServiceIntegrationTest {

    @Autowired
    private WebApplicationContext webApplicationContext;

    @Autowired
    private UserRoleRepository userRoleRepository;

    @Autowired
    private ObjectMapper objectMapper;

    private MockMvc mockMvc;

    @BeforeEach
    void setUp() {
        mockMvc = MockMvcBuilders.webAppContextSetup(webApplicationContext).build();
        
        // Create a test user with admin role
        UserRoleEntity adminRole = new UserRoleEntity();
        adminRole.setUserId("admin_user");
        adminRole.setRoleName("admin");
        adminRole.setProjectId(null); // Global role
        userRoleRepository.save(adminRole);
    }

    @Test
    void completeApprovalWorkflow() throws Exception {
        // 1. Create approval request
        ApprovalRequestDto request = new ApprovalRequestDto();
        request.setApprovalId("integration_test_001");
        request.setTaskId("task_integration_001");
        request.setAction("app.generate");
        request.setTool("command.exec");
        request.setCommand("mvn test");
        request.setRiskScore(0.7);

        String createResponse = mockMvc.perform(post("/api/v1/approvals")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.approvalId").value("integration_test_001"))
                .andExpect(jsonPath("$.taskId").value("task_integration_001"))
                .andExpect(jsonPath("$.decision").value("PENDING"))
                .andReturn()
                .getResponse()
                .getContentAsString();

        ApprovalResponseDto createdApproval = objectMapper.readValue(createResponse, ApprovalResponseDto.class);

        // 2. Get approval by ID
        mockMvc.perform(get("/api/v1/approvals/{approvalId}", createdApproval.getApprovalId()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.approvalId").value("integration_test_001"))
                .andExpect(jsonPath("$.decision").value("PENDING"));

        // 3. List pending approvals
        mockMvc.perform(get("/api/v1/approvals")
                .param("pendingOnly", "true"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[?(@.approvalId == 'integration_test_001')]").exists());

        // 4. Submit approval decision
        ApprovalDecisionDto decision = new ApprovalDecisionDto();
        decision.setDecision(ApprovalDecision.APPROVE);
        decision.setMessage("Integration test approval");

        mockMvc.perform(post("/api/v1/approvals/{approvalId}/decision", createdApproval.getApprovalId())
                .header("X-User-ID", "admin_user")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(decision)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.approvalId").value("integration_test_001"))
                .andExpect(jsonPath("$.decision").value("APPROVE"))
                .andExpect(jsonPath("$.decisionMessage").value("Integration test approval"))
                .andExpect(jsonPath("$.decidedBy").value("admin_user"));

        // 5. Verify approval is no longer pending
        mockMvc.perform(get("/api/v1/approvals/{approvalId}", createdApproval.getApprovalId()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.decision").value("APPROVE"))
                .andExpect(jsonPath("$.decidedBy").value("admin_user"));
    }

    @Test
    void healthCheckEndpoints() throws Exception {
        // Test custom health endpoint
        mockMvc.perform(get("/api/v1/approvals/health"))
                .andExpect(status().isOk())
                .andExpect(content().string("OK"));

        // Test Spring Boot actuator health endpoint
        mockMvc.perform(get("/actuator/health"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("UP"));
    }

    @Test
    void accessDeniedForUnauthorizedUser() throws Exception {
        // Create approval request
        ApprovalRequestDto request = new ApprovalRequestDto();
        request.setApprovalId("unauthorized_test_001");
        request.setTaskId("task_unauthorized_001");
        request.setAction("app.generate");
        request.setTool("command.exec");
        request.setCommand("mvn test");
        request.setRiskScore(0.8);

        String createResponse = mockMvc.perform(post("/api/v1/approvals")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isCreated())
                .andReturn()
                .getResponse()
                .getContentAsString();

        ApprovalResponseDto createdApproval = objectMapper.readValue(createResponse, ApprovalResponseDto.class);

        // Try to submit decision with unauthorized user
        ApprovalDecisionDto decision = new ApprovalDecisionDto();
        decision.setDecision(ApprovalDecision.APPROVE);
        decision.setMessage("Unauthorized attempt");

        mockMvc.perform(post("/api/v1/approvals/{approvalId}/decision", createdApproval.getApprovalId())
                .header("X-User-ID", "unauthorized_user")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(decision)))
                .andExpect(status().isForbidden());
    }
}