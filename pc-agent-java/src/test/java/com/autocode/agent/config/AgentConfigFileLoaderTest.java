package com.autocode.agent.config;

import org.junit.jupiter.api.Test;

import java.io.File;
import java.nio.file.Files;
import java.util.Properties;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
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

    @Test
    void loadOverridesReadsClientTlsOverrides() throws Exception {
        File tmp = File.createTempFile("agent-tls", ".properties");
        Files.writeString(tmp.toPath(), String.join("\n",
                "MVP_AGENT_TLS_KEYSTORE_PATH=D:/certs/client.p12",
                "MVP_AGENT_TLS_KEYSTORE_PASSWORD=changeit",
                "MVP_AGENT_TLS_KEYSTORE_TYPE=PKCS12",
                "MVP_AGENT_TLS_TRUSTSTORE_PATH=D:/certs/trust.jks",
                "MVP_AGENT_TLS_TRUSTSTORE_PASSWORD=trustit",
                "MVP_AGENT_TLS_TRUSTSTORE_TYPE=JKS",
                ""));

        AgentConfigFileLoader loader = new AgentConfigFileLoader();
        AgentConfig cfg = loader.loadOverrides(tmp);
        AgentConfig.ClientTls tls = cfg.getClientTls();
        assertTrue(tls.isKeyMaterialConfigured());
        assertEquals("D:/certs/client.p12", tls.getKeyStorePath());
        assertEquals("changeit", tls.getKeyStorePassword());
        assertEquals("PKCS12", tls.getKeyStoreType());
        assertEquals("D:/certs/trust.jks", tls.getTrustStorePath());
        assertEquals("trustit", tls.getTrustStorePassword());
        assertEquals("JKS", tls.getTrustStoreType());
    }

    @Test
    void loadOverridesKeepsBaseTlsValuesWhenTlsKeysUnset() throws Exception {
        AgentConfig base = AgentConfig.fromEnv();
        File tmp = File.createTempFile("agent-tls-base", ".properties");
        Files.writeString(tmp.toPath(), "MVP_AGENT_TLS_KEYSTORE_PATH=D:/certs/client.p12\n");

        AgentConfigFileLoader loader = new AgentConfigFileLoader();
        AgentConfig cfg = loader.loadOverrides(tmp);
        AgentConfig.ClientTls tls = cfg.getClientTls();

        assertEquals("D:/certs/client.p12", tls.getKeyStorePath());
        assertEquals(base.getClientTls().getKeyStorePassword(), tls.getKeyStorePassword());
        assertEquals(base.getClientTls().getKeyStoreType(), tls.getKeyStoreType());
        assertEquals(base.getClientTls().getTrustStorePath(), tls.getTrustStorePath());
        assertEquals(base.getClientTls().getTrustStorePassword(), tls.getTrustStorePassword());
        assertEquals(base.getClientTls().getTrustStoreType(), tls.getTrustStoreType());
    }

    @Test
    void clientTlsMergeDisablesKeyMaterialWhenKeystorePathBlank() {
        Properties enable = new Properties();
        enable.setProperty("MVP_AGENT_TLS_KEYSTORE_PATH", "D:/certs/client.p12");
        enable.setProperty("MVP_AGENT_TLS_TRUSTSTORE_PATH", "D:/certs/trust.jks");
        AgentConfig.ClientTls configured = AgentConfig.ClientTls.mergeFromProperties(AgentConfig.ClientTls.disabled(), enable);
        assertTrue(configured.isKeyMaterialConfigured());

        Properties disable = new Properties();
        disable.setProperty("MVP_AGENT_TLS_KEYSTORE_PATH", "   ");
        AgentConfig.ClientTls disabled = AgentConfig.ClientTls.mergeFromProperties(configured, disable);
        assertFalse(disabled.isKeyMaterialConfigured());
        assertEquals(null, disabled.getKeyStorePath());
        assertEquals(null, disabled.getTrustStorePath());
    }
}

