/**
 * Builds TLS settings for {@link okhttp3.OkHttpClient} when a client certificate is configured
 * (mTLS toward the control plane).
 */
package com.autocode.agent.client;

import com.autocode.agent.config.AgentConfig;
import okhttp3.OkHttpClient;

import javax.net.ssl.KeyManagerFactory;
import javax.net.ssl.SSLContext;
import javax.net.ssl.SSLSocketFactory;
import javax.net.ssl.TrustManager;
import javax.net.ssl.TrustManagerFactory;
import javax.net.ssl.X509TrustManager;
import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.GeneralSecurityException;
import java.security.KeyStore;
import java.security.SecureRandom;

final class AgentTlsSocketFactory {

    private AgentTlsSocketFactory() {
    }

    static void apply(OkHttpClient.Builder builder, AgentConfig.ClientTls tls)
            throws IOException, GeneralSecurityException {
        if (tls == null || !tls.isKeyMaterialConfigured()) {
            return;
        }
        KeyStore keyStore = KeyStore.getInstance(tls.getKeyStoreType());
        char[] keyPw = passwordChars(tls.getKeyStorePassword());
        try (InputStream in = Files.newInputStream(Path.of(tls.getKeyStorePath()))) {
            keyStore.load(in, keyPw);
        }
        KeyManagerFactory kmf = KeyManagerFactory.getInstance(KeyManagerFactory.getDefaultAlgorithm());
        kmf.init(keyStore, keyPw);

        TrustManagerFactory tmf = TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm());
        if (tls.getTrustStorePath() != null && !tls.getTrustStorePath().isBlank()) {
            KeyStore trustStore = KeyStore.getInstance(tls.getTrustStoreType());
            char[] trustPw = passwordChars(tls.getTrustStorePassword());
            try (InputStream in = Files.newInputStream(Path.of(tls.getTrustStorePath().trim()))) {
                trustStore.load(in, trustPw);
            }
            tmf.init(trustStore);
        } else {
            tmf.init((KeyStore) null);
        }

        TrustManager[] trustManagers = tmf.getTrustManagers();
        X509TrustManager x509TrustManager = null;
        for (TrustManager tm : trustManagers) {
            if (tm instanceof X509TrustManager) {
                x509TrustManager = (X509TrustManager) tm;
                break;
            }
        }
        if (x509TrustManager == null) {
            throw new IllegalStateException("No X509TrustManager available after TLS trust configuration");
        }

        SSLContext sslContext = SSLContext.getInstance("TLS");
        sslContext.init(kmf.getKeyManagers(), trustManagers, new SecureRandom());
        SSLSocketFactory socketFactory = sslContext.getSocketFactory();
        builder.sslSocketFactory(socketFactory, x509TrustManager);
    }

    private static char[] passwordChars(String password) {
        if (password == null || password.isEmpty()) {
            return null;
        }
        return password.toCharArray();
    }
}
