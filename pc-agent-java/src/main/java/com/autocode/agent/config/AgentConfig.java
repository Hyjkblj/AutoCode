/**
 * Agent runtime configuration loaded from environment variables.
 */
package com.autocode.agent.config;

import java.util.Arrays;
import java.util.List;

public class AgentConfig {
    private final String baseUrl;
    private final String nodeId;
    private final String agentToken;
    private final long pollIntervalMs;
    private final long heartbeatIntervalMs;
    private final long approvalTimeoutSeconds;
    private final List<String> allowedCommandPrefixes;
    private final List<String> allowedWorkspacePrefixes;
    private final String agentProfile;

    public AgentConfig(
            String baseUrl,
            String nodeId,
            String agentToken,
            long pollIntervalMs,
            long heartbeatIntervalMs,
            long approvalTimeoutSeconds,
            List<String> allowedCommandPrefixes,
            List<String> allowedWorkspacePrefixes,
            String agentProfile
    ) {
        this.baseUrl = baseUrl;
        this.nodeId = nodeId;
        this.agentToken = agentToken;
        this.pollIntervalMs = pollIntervalMs;
        this.heartbeatIntervalMs = heartbeatIntervalMs;
        this.approvalTimeoutSeconds = approvalTimeoutSeconds;
        this.allowedCommandPrefixes = allowedCommandPrefixes;
        this.allowedWorkspacePrefixes = allowedWorkspacePrefixes;
        this.agentProfile = agentProfile;
    }

    public static AgentConfig fromEnv() {
        String baseUrl = read("MVP_BASE_URL", "http://localhost:8048");
        String nodeId = read("MVP_NODE_ID", "node-local-1");
        String agentToken = read("MVP_AGENT_TOKEN", "agent-dev-token");
        long pollInterval = Long.parseLong(read("MVP_POLL_INTERVAL_MS", "1500"));
        long heartbeatInterval = Long.parseLong(read("MVP_HEARTBEAT_INTERVAL_MS", "10000"));
        long approvalTimeout = Long.parseLong(read("MVP_APPROVAL_TIMEOUT_SECONDS", "120"));
        List<String> allowedCommands = Arrays.stream(read(
                        "MVP_ALLOWED_COMMAND_PREFIXES",
                        "git status,git diff,git push,echo,mvn test,mvn -q test,mvn -q -DskipTests package,npm test,gradle test"
                ).split(","))
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .toList();
        List<String> allowedWorkspaces = Arrays.stream(read("MVP_ALLOWED_WORKSPACE_PREFIXES", "").split(","))
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .toList();
        String agentProfile = read("MVP_AGENT_PROFILE", "coder").trim().toLowerCase();
        return new AgentConfig(baseUrl, nodeId, agentToken, pollInterval, heartbeatInterval, approvalTimeout, allowedCommands, allowedWorkspaces, agentProfile);
    }

    private static String read(String key, String fallback) {
        String value = System.getenv(key);
        if (value == null || value.isBlank()) {
            return fallback;
        }
        return value;
    }

    public String getBaseUrl() {
        return baseUrl;
    }

    public String getNodeId() {
        return nodeId;
    }

    public String getAgentToken() {
        return agentToken;
    }

    public long getPollIntervalMs() {
        return pollIntervalMs;
    }

    public long getHeartbeatIntervalMs() {
        return heartbeatIntervalMs;
    }

    public long getApprovalTimeoutSeconds() {
        return approvalTimeoutSeconds;
    }

    public List<String> getAllowedCommandPrefixes() {
        return allowedCommandPrefixes;
    }

    public List<String> getAllowedWorkspacePrefixes() {
        return allowedWorkspacePrefixes;
    }

    public String getAgentProfile() {
        return agentProfile;
    }
}
