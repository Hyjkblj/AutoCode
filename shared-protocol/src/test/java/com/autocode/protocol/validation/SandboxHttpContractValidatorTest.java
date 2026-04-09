package com.autocode.protocol.validation;

import com.autocode.protocol.model.SandboxErrorResponse;
import com.autocode.protocol.model.SandboxHealthResponse;
import com.autocode.protocol.model.SandboxToolsResponse;
import com.autocode.protocol.model.ToolManifest;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.io.InputStream;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;

class SandboxHttpContractValidatorTest {
    private static final ObjectMapper MAPPER = new ObjectMapper().findAndRegisterModules();

    @Test
    void health_example_resource_is_valid() throws Exception {
        try (InputStream in = SandboxHttpContractValidatorTest.class.getResourceAsStream("/examples/sandbox_health_response.v1.example.json")) {
            assertNotNull(in, "Missing test resource: /examples/sandbox_health_response.v1.example.json");
            SandboxHealthResponse response = MAPPER.readValue(in, SandboxHealthResponse.class);
            assertDoesNotThrow(() -> SandboxHttpContractValidator.validateHealthResponse(response));
        }
    }

    @Test
    void error_example_resource_is_valid() throws Exception {
        try (InputStream in = SandboxHttpContractValidatorTest.class.getResourceAsStream("/examples/sandbox_error_response.v1.example.json")) {
            assertNotNull(in, "Missing test resource: /examples/sandbox_error_response.v1.example.json");
            SandboxErrorResponse response = MAPPER.readValue(in, SandboxErrorResponse.class);
            assertDoesNotThrow(() -> SandboxHttpContractValidator.validateErrorResponse(response));
        }
    }

    @Test
    void health_requires_status() {
        SandboxHealthResponse response = new SandboxHealthResponse();
        response.setOk(true);
        assertThrows(ContractViolationException.class, () -> SandboxHttpContractValidator.validateHealthResponse(response));
    }

    @Test
    void error_requires_error_field() {
        SandboxErrorResponse response = new SandboxErrorResponse();
        response.setStatus("invalid_request");
        assertThrows(ContractViolationException.class, () -> SandboxHttpContractValidator.validateErrorResponse(response));
    }

    @Test
    void health_requires_ok_true() {
        SandboxHealthResponse response = new SandboxHealthResponse();
        response.setOk(false);
        response.setStatus("up");
        assertThrows(ContractViolationException.class, () -> SandboxHttpContractValidator.validateHealthResponse(response));
    }

    @Test
    void error_requires_ok_false() {
        SandboxErrorResponse response = new SandboxErrorResponse();
        response.setOk(true);
        response.setStatus("invalid_request");
        response.setError("taskId is required");
        assertThrows(ContractViolationException.class, () -> SandboxHttpContractValidator.validateErrorResponse(response));
    }

    @Test
    void tools_example_resource_is_valid() throws Exception {
        try (InputStream in = SandboxHttpContractValidatorTest.class.getResourceAsStream("/examples/sandbox_tools_response.v1.example.json")) {
            assertNotNull(in, "Missing test resource: /examples/sandbox_tools_response.v1.example.json");
            SandboxToolsResponse response = MAPPER.readValue(in, SandboxToolsResponse.class);
            assertDoesNotThrow(() -> SandboxHttpContractValidator.validateToolsResponse(response));
        }
    }

    @Test
    void tools_requires_ok_true() {
        SandboxToolsResponse response = new SandboxToolsResponse();
        response.setOk(false);
        response.setTools(List.of(validManifest()));
        assertThrows(ContractViolationException.class, () -> SandboxHttpContractValidator.validateToolsResponse(response));
    }

    @Test
    void tools_requires_valid_manifest() {
        ToolManifest manifest = validManifest();
        manifest.setAction(" ");
        SandboxToolsResponse response = new SandboxToolsResponse();
        response.setOk(true);
        response.setTools(List.of(manifest));
        assertThrows(ContractViolationException.class, () -> SandboxHttpContractValidator.validateToolsResponse(response));
    }

    private static ToolManifest validManifest() {
        ToolManifest manifest = new ToolManifest();
        manifest.setName("command.exec");
        manifest.setVersion("1.0.0");
        manifest.setAction("run_command");
        return manifest;
    }
}
