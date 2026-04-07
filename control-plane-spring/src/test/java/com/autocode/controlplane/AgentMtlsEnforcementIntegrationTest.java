package com.autocode.controlplane;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import java.security.cert.X509Certificate;

import static org.mockito.Mockito.mock;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest(properties = {
        "mvp.mtls.required-for-agent=true"
})
@ActiveProfiles("test")
@AutoConfigureMockMvc
class AgentMtlsEnforcementIntegrationTest extends OperatorProj1MembershipFixture {

    @Autowired
    private MockMvc mockMvc;

    @Test
    void agentEndpointShouldReturn403WhenMtlsRequiredAndCertMissing() throws Exception {
        mockMvc.perform(get("/api/v1/agent/nodes")
                        .header("X-Agent-Token", "ag-a"))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.ok").value(false))
                .andExpect(jsonPath("$.error").value("mtls required for agent"));
    }

    @Test
    void agentEndpointShouldReturn403WhenContextPathPresentAndCertMissing() throws Exception {
        mockMvc.perform(get("/cp/api/v1/agent/nodes")
                        .contextPath("/cp")
                        .header("X-Agent-Token", "ag-a"))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.ok").value(false))
                .andExpect(jsonPath("$.error").value("mtls required for agent"));
    }

    @Test
    void agentEndpointShouldAllowWhenMtlsCertPresent() throws Exception {
        X509Certificate cert = mock(X509Certificate.class);
        mockMvc.perform(get("/api/v1/agent/nodes")
                        .header("X-Agent-Token", "ag-a")
                        .requestAttr("jakarta.servlet.request.X509Certificate", new X509Certificate[]{cert}))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true))
                .andExpect(jsonPath("$.payload").isArray());
    }

    @Test
    void operatorEndpointShouldNotRequireMtlsForAgentOnlyGate() throws Exception {
        String payload = """
                {
                  "projectId": "proj-1",
                  "assistant": "codex",
                  "prompt": "mtls scope check"
                }
                """;

        mockMvc.perform(post("/api/v1/tasks")
                        .header("Authorization", "Bearer op-a")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(payload))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true));
    }

    @Test
    void agentEndpointShouldStillRequireAgentTokenEvenWithCert() throws Exception {
        X509Certificate cert = mock(X509Certificate.class);
        mockMvc.perform(get("/api/v1/agent/nodes")
                        .requestAttr("jakarta.servlet.request.X509Certificate", new X509Certificate[]{cert}))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.ok").value(false))
                .andExpect(jsonPath("$.error").value("invalid agent token"));
    }
}
