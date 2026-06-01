package com.autocode.controlplane.security;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "mvp.auth.jwt")
public class JwtAuthProperties {
    /**
     * HMAC secret for signing JWT (base64 recommended). For dev only.
     */
    private String secret = "dev-secret-change-me-dev-secret-change-me";

    /**
     * Access token TTL seconds.
     */
    private long accessTtlSeconds = 900;

    /**
     * Refresh token TTL seconds (default 30 days).
     */
    private long refreshTtlSeconds = 2592000;

    public String getSecret() {
        return secret;
    }

    public void setSecret(String secret) {
        this.secret = secret;
    }

    public long getAccessTtlSeconds() {
        return accessTtlSeconds;
    }

    public void setAccessTtlSeconds(long accessTtlSeconds) {
        this.accessTtlSeconds = accessTtlSeconds;
    }

    public long getRefreshTtlSeconds() {
        return refreshTtlSeconds;
    }

    public void setRefreshTtlSeconds(long refreshTtlSeconds) {
        this.refreshTtlSeconds = refreshTtlSeconds;
    }
}
