package com.autocode.agent.config;

import org.junit.jupiter.api.Test;

import java.io.File;
import java.nio.file.Files;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class AgentConfigFileLoaderTest {
    @Test
    void loadOverridesReadsWorkspaceAllowlist() throws Exception {
        File tmp = File.createTempFile("agent", ".properties");
        Files.writeString(tmp.toPath(), "MVP_ALLOWED_WORKSPACE_PREFIXES=D:/repoA,D:/repoB\n");

        AgentConfigFileLoader loader = new AgentConfigFileLoader();
        AgentConfig cfg = loader.loadOverrides(tmp);
        assertEquals(2, cfg.getAllowedWorkspacePrefixes().size());
    }

    @Test
    void loadOverridesReadsIntentRules() throws Exception {
        File tmp = File.createTempFile("agent-intent", ".properties");
        Files.writeString(tmp.toPath(),
                "MVP_INTENT_RULES=profile=web|skill=skill.web;keywords=deploy,release|skill=skill.deploy|command=echo deploy\n");

        AgentConfigFileLoader loader = new AgentConfigFileLoader();
        AgentConfig cfg = loader.loadOverrides(tmp);
        assertEquals(2, cfg.getIntentRules().size());
        assertEquals("web", cfg.getIntentRules().get(0).profile());
        assertEquals("skill.web", cfg.getIntentRules().get(0).skill());
        assertTrue(cfg.getIntentRules().get(1).keywords().contains("deploy"));
        assertEquals("echo deploy", cfg.getIntentRules().get(1).command());
    }
}

