package com.autocode.protocol.model;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.io.InputStream;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class SandboxExecuteSerdeTest {
    private static final ObjectMapper MAPPER = new ObjectMapper().findAndRegisterModules();

    @Test
    void request_example_deserializes() throws Exception {
        try (InputStream in = SandboxExecuteSerdeTest.class.getResourceAsStream("/examples/sandbox_execute_request.v1.example.json")) {
            assertNotNull(in, "Missing test resource: /examples/sandbox_execute_request.v1.example.json");
            SandboxExecuteRequest request = MAPPER.readValue(in, SandboxExecuteRequest.class);
            assertEquals("task_test_123", request.getTaskId());
            assertEquals("echo sandbox_ok", request.getCommand());
            assertEquals("command.exec", request.getTool());
        }
    }

    @Test
    void response_example_deserializes() throws Exception {
        try (InputStream in = SandboxExecuteSerdeTest.class.getResourceAsStream("/examples/sandbox_execute_response.v1.example.json")) {
            assertNotNull(in, "Missing test resource: /examples/sandbox_execute_response.v1.example.json");
            SandboxExecuteResponse response = MAPPER.readValue(in, SandboxExecuteResponse.class);
            assertTrue(response.isOk());
            assertEquals("ok", response.getStatus());
            assertEquals(0, response.getExitCode());
        }
    }

    @Test
    void health_response_example_deserializes() throws Exception {
        try (InputStream in = SandboxExecuteSerdeTest.class.getResourceAsStream("/examples/sandbox_health_response.v1.example.json")) {
            assertNotNull(in, "Missing test resource: /examples/sandbox_health_response.v1.example.json");
            SandboxHealthResponse response = MAPPER.readValue(in, SandboxHealthResponse.class);
            assertTrue(response.isOk());
            assertEquals("up", response.getStatus());
        }
    }

    @Test
    void error_response_example_deserializes() throws Exception {
        try (InputStream in = SandboxExecuteSerdeTest.class.getResourceAsStream("/examples/sandbox_error_response.v1.example.json")) {
            assertNotNull(in, "Missing test resource: /examples/sandbox_error_response.v1.example.json");
            SandboxErrorResponse response = MAPPER.readValue(in, SandboxErrorResponse.class);
            assertEquals("invalid_request", response.getStatus());
            assertEquals("taskId is required", response.getError());
        }
    }
}
