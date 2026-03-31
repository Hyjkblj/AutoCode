/**
 * Token-based auth settings for operator and agent calls.
 */
package com.autocode.controlplane.security;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

@ConfigurationProperties(prefix = "mvp.auth")
public class AuthProperties {
    private String operatorToken = "operator-dev-token";
    private String agentToken = "agent-dev-token";

    /**
     * Comma-separated tokens for rotation. When empty, falls back to operatorToken/agentToken.
     */
    private String operatorTokens;
    private String agentTokens;

    /**
     * Comma-separated revoked tokens (applies to both operator and agent).
     */
    private String revokedTokens;

    public String getOperatorToken() {
        return operatorToken;
    }

    public void setOperatorToken(String operatorToken) {
        this.operatorToken = operatorToken;
    }

    public String getAgentToken() {
        return agentToken;
    }

    public void setAgentToken(String agentToken) {
        this.agentToken = agentToken;
    }

    public String getOperatorTokens() {
        return operatorTokens;
    }

    public void setOperatorTokens(String operatorTokens) {
        this.operatorTokens = operatorTokens;
    }

    public String getAgentTokens() {
        return agentTokens;
    }

    public void setAgentTokens(String agentTokens) {
        this.agentTokens = agentTokens;
    }

    public String getRevokedTokens() {
        return revokedTokens;
    }

    public void setRevokedTokens(String revokedTokens) {
        this.revokedTokens = revokedTokens;
    }

    public List<String> operatorTokenList() {
        List<String> list = split(operatorTokens);
        if (!list.isEmpty()) {
            return list;
        }
        return List.of(operatorToken);
    }

    public List<String> agentTokenList() {
        List<String> list = split(agentTokens);
        if (!list.isEmpty()) {
            return list;
        }
        return List.of(agentToken);
    }

    public List<String> revokedTokenList() {
        return split(revokedTokens);
    }

    private List<String> split(String value) {
        if (value == null || value.isBlank()) {
            return List.of();
        }
        List<String> out = new ArrayList<>();
        Arrays.stream(value.split(","))
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .forEach(out::add);
        return out;
    }
}
