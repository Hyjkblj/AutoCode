package com.autocode.agent.config;

import org.junit.jupiter.api.Test;

import java.io.File;
import java.nio.file.Files;

import static org.junit.jupiter.api.Assertions.assertEquals;

class AgentConfigFileLoaderTest {
    @Test
    void loadOverridesReadsWorkspaceAllowlist() throws Exception {
        File tmp = File.createTempFile("agent", ".properties");
        Files.writeString(tmp.toPath(), "MVP_ALLOWED_WORKSPACE_PREFIXES=D:/repoA,D:/repoB\n");

        AgentConfigFileLoader loader = new AgentConfigFileLoader();
        AgentConfig cfg = loader.loadOverrides(tmp);
        assertEquals(2, cfg.getAllowedWorkspacePrefixes().size());
    }
}

