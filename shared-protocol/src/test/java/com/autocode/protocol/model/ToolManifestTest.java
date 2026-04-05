package com.autocode.protocol.model;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;

class ToolManifestTest {
    private static final ObjectMapper MAPPER = new ObjectMapper().findAndRegisterModules();

    @Test
    void serdeRoundtripKeepsManifestAndPermissions() throws Exception {
        ToolManifest manifest = new ToolManifest();
        manifest.setName("command.exec");
        manifest.setVersion("1.0.0");
        manifest.setDescription("Execute shell command");
        manifest.setAction("run_command");
        manifest.setArgsSchema(Map.of(
                "type", "object",
                "required", List.of("command")
        ));

        ToolParamSpec command = new ToolParamSpec();
        command.setName("command");
        command.setType("string");
        command.setRequired(true);
        command.setDescription("Command to run");
        manifest.setParams(List.of(command));

        ToolPermissions permissions = new ToolPermissions();
        permissions.setCommandExec(true);
        permissions.setApprovalRequired(true);
        permissions.setRiskScore(0.91d);
        permissions.setRequiredPolicies(List.of("workspace.allowlist", "approval.gate"));
        manifest.setPermissions(permissions);

        String json = MAPPER.writeValueAsString(manifest);
        ToolManifest restored = MAPPER.readValue(json, ToolManifest.class);
        assertEquals("command.exec", restored.getName());
        assertEquals("1.0.0", restored.getVersion());
        assertEquals("run_command", restored.getAction());
        assertNotNull(restored.getParams());
        assertEquals(1, restored.getParams().size());
        assertEquals("command", restored.getParams().get(0).getName());
        assertNotNull(restored.getPermissions());
        assertEquals(0.91d, restored.getPermissions().getRiskScore());
        assertEquals(List.of("workspace.allowlist", "approval.gate"), restored.getPermissions().getRequiredPolicies());
    }
}
