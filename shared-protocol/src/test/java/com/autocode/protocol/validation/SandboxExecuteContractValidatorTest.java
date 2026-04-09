package com.autocode.protocol.validation;

import com.autocode.protocol.model.SandboxExecuteRequest;
import com.autocode.protocol.model.SandboxExecuteResponse;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.io.InputStream;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;

class SandboxExecuteContractValidatorTest {
    private static final ObjectMapper MAPPER = new ObjectMapper().findAndRegisterModules();

    @Test
    void request_example_resource_is_valid() throws Exception {
        try (InputStream in = SandboxExecuteContractValidatorTest.class.getResourceAsStream("/examples/sandbox_execute_request.v1.example.json")) {
            assertNotNull(in, "Missing test resource: /examples/sandbox_execute_request.v1.example.json");
            SandboxExecuteRequest request = MAPPER.readValue(in, SandboxExecuteRequest.class);
            assertDoesNotThrow(() -> SandboxExecuteContractValidator.validateRequest(request));
        }
    }

    @Test
    void response_example_resource_is_valid() throws Exception {
        try (InputStream in = SandboxExecuteContractValidatorTest.class.getResourceAsStream("/examples/sandbox_execute_response.v1.example.json")) {
            assertNotNull(in, "Missing test resource: /examples/sandbox_execute_response.v1.example.json");
            SandboxExecuteResponse response = MAPPER.readValue(in, SandboxExecuteResponse.class);
            assertDoesNotThrow(() -> SandboxExecuteContractValidator.validateResponse(response));
        }
    }

    @Test
    void request_requires_taskId_and_command() {
        SandboxExecuteRequest request = new SandboxExecuteRequest();
        request.setTaskId("task_1");
        assertThrows(ContractViolationException.class, () -> SandboxExecuteContractValidator.validateRequest(request));
    }

    @Test
    void request_rejects_non_positive_timeout() {
        SandboxExecuteRequest request = new SandboxExecuteRequest();
        request.setTaskId("task_1");
        request.setCommand("echo hello");
        request.setApprovalTimeoutSeconds(0L);
        assertThrows(ContractViolationException.class, () -> SandboxExecuteContractValidator.validateRequest(request));
    }

    @Test
    void success_response_requires_tool() {
        SandboxExecuteResponse response = new SandboxExecuteResponse();
        response.setOk(true);
        response.setStatus("ok");
        response.setRetryable(false);
        assertThrows(ContractViolationException.class, () -> SandboxExecuteContractValidator.validateResponse(response));
    }
}
