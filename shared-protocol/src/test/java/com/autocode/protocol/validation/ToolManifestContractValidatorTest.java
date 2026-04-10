package com.autocode.protocol.validation;

import com.autocode.protocol.model.ToolManifest;
import com.autocode.protocol.model.ToolParamSpec;
import com.autocode.protocol.model.ToolPermissions;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.io.InputStream;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;

class ToolManifestContractValidatorTest {
    private static final ObjectMapper MAPPER = new ObjectMapper().findAndRegisterModules();

    @Test
    void tool_manifest_example_resource_is_valid() throws Exception {
        try (InputStream in = ToolManifestContractValidatorTest.class.getResourceAsStream("/examples/tool_manifest.v1.example.json")) {
            assertNotNull(in, "Missing test resource: /examples/tool_manifest.v1.example.json");
            ToolManifest manifest = MAPPER.readValue(in, ToolManifest.class);
            assertDoesNotThrow(() -> ToolManifestContractValidator.validate(manifest));
        }
    }

    @Test
    void missing_action_is_rejected() {
        ToolManifest manifest = validManifest();
        manifest.setAction(" ");
        assertThrows(ContractViolationException.class, () -> ToolManifestContractValidator.validate(manifest));
    }

    @Test
    void duplicate_param_names_are_rejected() {
        ToolManifest manifest = validManifest();
        ToolParamSpec p1 = new ToolParamSpec();
        p1.setName("command");
        ToolParamSpec p2 = new ToolParamSpec();
        p2.setName("command");
        manifest.setParams(List.of(p1, p2));
        assertThrows(ContractViolationException.class, () -> ToolManifestContractValidator.validate(manifest));
    }

    @Test
    void risk_score_out_of_range_is_rejected() {
        ToolManifest manifest = validManifest();
        ToolPermissions permissions = new ToolPermissions();
        permissions.setRiskScore(1.2d);
        manifest.setPermissions(permissions);
        assertThrows(ContractViolationException.class, () -> ToolManifestContractValidator.validate(manifest));
    }

    @Test
    void blank_required_policy_is_rejected() {
        ToolManifest manifest = validManifest();
        ToolPermissions permissions = new ToolPermissions();
        permissions.setRiskScore(0.2d);
        permissions.setRequiredPolicies(List.of("workspace.allowlist", " "));
        manifest.setPermissions(permissions);
        assertThrows(ContractViolationException.class, () -> ToolManifestContractValidator.validate(manifest));
    }

    private static ToolManifest validManifest() {
        ToolManifest manifest = new ToolManifest();
        manifest.setName("command.exec");
        manifest.setVersion("1.0.0");
        manifest.setAction("run_command");
        return manifest;
    }
}
