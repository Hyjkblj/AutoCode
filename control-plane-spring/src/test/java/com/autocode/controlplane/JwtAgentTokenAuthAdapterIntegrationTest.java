package com.autocode.controlplane;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest(properties = {
        "mvp.auth.mode=jwt",
        "mvp.auth.jwt.secret=01234567890123456789012345678901",
        "mvp.auth.agent-tokens=ag-a,ag-b",
        "mvp.auth.revoked-tokens=ag-b"
})
@ActiveProfiles("test")
@AutoConfigureMockMvc
class JwtAgentTokenAuthAdapterIntegrationTest {

    @Autowired
    private MockMvc mockMvc;

    @Test
    void validAgentTokenShouldAccessAgentApiInJwtMode() throws Exception {
        String payload = """
                {
                  "nodeId": "node_jwt_adapter_1",
                  "version": "1.0.0"
                }
                """;

        mockMvc.perform(post("/api/v1/agent/register")
                        .header("X-Agent-Token", "ag-a")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(payload))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true))
                .andExpect(jsonPath("$.payload.nodeId").value("node_jwt_adapter_1"));
    }

    @Test
    void revokedAgentTokenShouldBeRejectedInJwtMode() throws Exception {
        String payload = """
                {
                  "nodeId": "node_jwt_adapter_2",
                  "version": "1.0.0"
                }
                """;

        mockMvc.perform(post("/api/v1/agent/register")
                        .header("X-Agent-Token", "ag-b")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(payload))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void validAgentTokenShouldPassAuthForArtifactUploadEndpointInJwtMode() throws Exception {
        MockMultipartFile file = new MockMultipartFile(
                "file",
                "demo.txt",
                MediaType.TEXT_PLAIN_VALUE,
                "hello".getBytes()
        );

        mockMvc.perform(multipart("/api/v1/tasks/{taskId}/artifacts", "tsk_missing")
                        .file(file)
                        .param("name", "demo.txt")
                        .header("X-Agent-Token", "ag-a"))
                // No permission error means auth adapter worked; missing task should map to 404.
                .andExpect(status().isNotFound());
    }
}
