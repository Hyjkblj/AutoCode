package com.autocode.agent.client;

import com.autocode.agent.config.AgentConfig;
import okhttp3.OkHttpClient;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.io.OutputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.KeyStore;
import java.util.Properties;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class AgentTlsSocketFactoryTest {

    @Test
    void applySkipsWhenTlsDisabled() {
        OkHttpClient.Builder builder = new OkHttpClient.Builder();
        assertDoesNotThrow(() -> AgentTlsSocketFactory.apply(builder, AgentConfig.ClientTls.disabled()));
    }

    @Test
    void applySupportsTrustStoreOnly() throws Exception {
        Path truststore = createEmptyTrustStoreFile("changeit");
        AgentConfig.ClientTls tls = tlsFromProperties(properties(
                "MVP_AGENT_TLS_TRUSTSTORE_PATH", truststore.toString(),
                "MVP_AGENT_TLS_TRUSTSTORE_PASSWORD", "changeit",
                "MVP_AGENT_TLS_TRUSTSTORE_TYPE", "JKS"
        ));
        assertTrue(tls.isTrustMaterialConfigured());

        OkHttpClient.Builder builder = new OkHttpClient.Builder();
        assertDoesNotThrow(() -> AgentTlsSocketFactory.apply(builder, tls));
    }

    @Test
    void applyFailsWhenTrustStorePathMissing() {
        AgentConfig.ClientTls tls = tlsFromProperties(properties(
                "MVP_AGENT_TLS_TRUSTSTORE_PATH", "Z:/not-exists/trust.jks",
                "MVP_AGENT_TLS_TRUSTSTORE_PASSWORD", "changeit",
                "MVP_AGENT_TLS_TRUSTSTORE_TYPE", "JKS"
        ));

        OkHttpClient.Builder builder = new OkHttpClient.Builder();
        assertThrows(IOException.class, () -> AgentTlsSocketFactory.apply(builder, tls));
    }

    @Test
    void applyFailsWhenKeyStorePathMissing() {
        AgentConfig.ClientTls tls = tlsFromProperties(properties(
                "MVP_AGENT_TLS_KEYSTORE_PATH", "Z:/not-exists/client.p12",
                "MVP_AGENT_TLS_KEYSTORE_PASSWORD", "changeit",
                "MVP_AGENT_TLS_KEYSTORE_TYPE", "PKCS12"
        ));

        OkHttpClient.Builder builder = new OkHttpClient.Builder();
        assertThrows(IOException.class, () -> AgentTlsSocketFactory.apply(builder, tls));
    }

    private static AgentConfig.ClientTls tlsFromProperties(Properties props) {
        return AgentConfig.ClientTls.mergeFromProperties(AgentConfig.ClientTls.disabled(), props);
    }

    private static Properties properties(String... kvs) {
        Properties props = new Properties();
        for (int i = 0; i + 1 < kvs.length; i += 2) {
            props.setProperty(kvs[i], kvs[i + 1]);
        }
        return props;
    }

    private static Path createEmptyTrustStoreFile(String password) throws Exception {
        Path file = Files.createTempFile("agent-tls-test", ".jks");
        KeyStore trustStore = KeyStore.getInstance("JKS");
        char[] pw = password.toCharArray();
        trustStore.load(null, pw);
        try (OutputStream out = Files.newOutputStream(file)) {
            trustStore.store(out, pw);
        }
        return file;
    }
}
