package com.autocode.agent.runtime.tool;

import com.autocode.protocol.model.ToolManifest;
import com.autocode.protocol.model.ToolPermissions;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ToolRegistryTest {
    @Test
    void getRequiredThrowsWhenMissing() {
        ToolRegistry registry = new ToolRegistry();
        IllegalArgumentException ex = assertThrows(IllegalArgumentException.class, () -> registry.getRequired("missing"));
        assertTrue(ex.getMessage().contains("unknown tool"));
    }

    @Test
    void versionedLookupReturnsExactVersion() {
        ToolRegistry registry = new ToolRegistry();
        Tool v1 = fakeTool("command.exec", "1.0.0");
        Tool v2 = fakeTool("command.exec", "1.1.0");
        registry.register(v1).register(v2);

        assertSame(v1, registry.getRequired("command.exec", "1.0.0"));
        assertSame(v2, registry.getRequired("command.exec", "1.1.0"));
    }

    @Test
    void lookupWithoutVersionReturnsLatest() {
        ToolRegistry registry = new ToolRegistry();
        Tool v1 = fakeTool("command.exec", "1.0.9");
        Tool v2 = fakeTool("command.exec", "1.2.0");
        registry.register(v1).register(v2);

        assertSame(v2, registry.getRequired("command.exec"));
    }

    @Test
    void listManifestsReturnsAllRegisteredVariants() {
        ToolRegistry registry = new ToolRegistry();
        registry.register(fakeTool("command.exec", "1.0.0"));
        registry.register(fakeTool("deploy.execute", "2.0.0"));

        List<ToolManifest> manifests = registry.listManifests();
        assertEquals(2, manifests.size());
        assertEquals("command.exec", manifests.get(0).getName());
        assertEquals("deploy.execute", manifests.get(1).getName());
    }

    @Test
    void registerRejectsMissingActionFromManifestContract() {
        ToolRegistry registry = new ToolRegistry();
        ToolManifest manifest = new ToolManifest();
        manifest.setName("command.exec");
        manifest.setVersion("1.0.0");

        Tool invalid = fakeTool(manifest);
        assertThrows(IllegalArgumentException.class, () -> registry.register(invalid));
    }

    @Test
    void registerRejectsOutOfRangeRiskScoreFromManifestContract() {
        ToolRegistry registry = new ToolRegistry();
        ToolManifest manifest = new ToolManifest();
        manifest.setName("command.exec");
        manifest.setVersion("1.0.0");
        manifest.setAction("run_command");
        ToolPermissions permissions = new ToolPermissions();
        permissions.setRiskScore(1.5d);
        manifest.setPermissions(permissions);

        Tool invalid = fakeTool(manifest);
        assertThrows(IllegalArgumentException.class, () -> registry.register(invalid));
    }

    private static Tool fakeTool(String name, String version) {
        ToolManifest manifest = new ToolManifest();
        manifest.setName(name);
        manifest.setVersion(version);
        manifest.setAction("run_command");
        ToolPermissions permissions = new ToolPermissions();
        permissions.setRiskScore(0.1d);
        manifest.setPermissions(permissions);
        return fakeTool(manifest);
    }

    private static Tool fakeTool(ToolManifest manifest) {
        return new Tool() {
            @Override
            public ToolManifest manifest() {
                return manifest;
            }

            @Override
            public ToolPolicy policy() {
                return new ToolPolicy() {
                    @Override
                    public boolean isAllowed(ToolCall call) {
                        return true;
                    }

                    @Override
                    public boolean requiresApproval(ToolCall call) {
                        return false;
                    }
                };
            }

            @Override
            public Map<String, Object> buildApprovalPayload(ToolCall call, ToolContext context) {
                return Map.of();
            }

            @Override
            public ToolExecutionResult execute(ToolCall call, ToolContext context) {
                return new ToolExecutionResult(Map.of("status", "ok"), true, false);
            }
        };
    }
}

