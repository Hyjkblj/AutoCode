package com.autocode.controlplane;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import static org.hamcrest.Matchers.hasItem;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@ActiveProfiles("test")
@AutoConfigureMockMvc
class AgentControllerIntegrationTest {

    @Autowired
    private MockMvc mockMvc;

    @Test
    void registerShouldPersistCapabilitiesAndExposeViaNodesList() throws Exception {
        String capabilities = "{\"profiles\":[\"ai-agent\",\"coder\"],\"runtime\":{\"lang\":\"python\",\"version\":\"3.12\"}}";

        String payload = """
                {
                  "nodeId": "node_cap_1",
                  "version": "1.2.3",
                  "capabilities": "%s"
                }
                """.formatted(capabilities.replace("\"", "\\\""));

        mockMvc.perform(post("/api/v1/agent/register")
                        .header("X-Agent-Token", "ag-a")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(payload))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true))
                .andExpect(jsonPath("$.payload.nodeId").value("node_cap_1"))
                .andExpect(jsonPath("$.payload.version").value("1.2.3"))
                .andExpect(jsonPath("$.payload.online").value(true))
                .andExpect(jsonPath("$.payload.capabilities").value(capabilities));

        mockMvc.perform(get("/api/v1/agent/nodes")
                        .header("X-Agent-Token", "ag-a"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true))
                .andExpect(jsonPath("$.payload[*].nodeId", hasItem("node_cap_1")))
                .andExpect(jsonPath("$.payload[*].capabilities", hasItem(capabilities)));
    }

    @Test
    void registerShouldAllowCapabilitiesOmitted() throws Exception {
        String payload = """
                {
                  "nodeId": "node_cap_2",
                  "version": "2.0.0"
                }
                """;

        mockMvc.perform(post("/api/v1/agent/register")
                        .header("X-Agent-Token", "ag-a")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(payload))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true))
                .andExpect(jsonPath("$.payload.nodeId").value("node_cap_2"))
                .andExpect(jsonPath("$.payload.version").value("2.0.0"));

        mockMvc.perform(get("/api/v1/agent/nodes")
                        .header("X-Agent-Token", "ag-a"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true))
                .andExpect(jsonPath("$.payload[*].nodeId", hasItem("node_cap_2")));
    }

    @Test
    void registerShouldRejectOperatorTokenWithoutAgentToken() throws Exception {
        String payload = """
                {
                  "nodeId": "node_cap_3",
                  "version": "3.0.0"
                }
                """;

        mockMvc.perform(post("/api/v1/agent/register")
                        .header("Authorization", "Bearer op-a")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(payload))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.ok").value(false))
                .andExpect(jsonPath("$.error").value("invalid agent token"));
    }
}
