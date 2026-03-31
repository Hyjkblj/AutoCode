package com.autocode.agent.config;

import java.io.File;
import java.io.FileInputStream;
import java.io.InputStream;
import java.util.Arrays;
import java.util.List;
import java.util.Properties;

/**
 * Loads agent configuration overrides from a simple .properties file.
 *
 * Keys reuse the same names as env vars, e.g. MVP_ALLOWED_COMMAND_PREFIXES.
 */
public class AgentConfigFileLoader {
    public AgentConfig loadOverrides(File file) {
        if (file == null || !file.exists() || !file.isFile()) {
            return null;
        }
        Properties props = new Properties();
        try (InputStream in = new FileInputStream(file)) {
            props.load(in);
        } catch (Exception e) {
            return null;
        }

        AgentConfig base = AgentConfig.fromEnv();

        String pollIntervalMs = props.getProperty("MVP_POLL_INTERVAL_MS");
        String heartbeatIntervalMs = props.getProperty("MVP_HEARTBEAT_INTERVAL_MS");
        String approvalTimeoutSeconds = props.getProperty("MVP_APPROVAL_TIMEOUT_SECONDS");

        List<String> allowedCommands = splitList(props.getProperty("MVP_ALLOWED_COMMAND_PREFIXES"));
        List<String> allowedWorkspaces = splitList(props.getProperty("MVP_ALLOWED_WORKSPACE_PREFIXES"));

        return new AgentConfig(
                base.getBaseUrl(),
                base.getNodeId(),
                base.getAgentToken(),
                pollIntervalMs == null ? base.getPollIntervalMs() : Long.parseLong(pollIntervalMs.trim()),
                heartbeatIntervalMs == null ? base.getHeartbeatIntervalMs() : Long.parseLong(heartbeatIntervalMs.trim()),
                approvalTimeoutSeconds == null ? base.getApprovalTimeoutSeconds() : Long.parseLong(approvalTimeoutSeconds.trim()),
                allowedCommands == null ? base.getAllowedCommandPrefixes() : allowedCommands,
                allowedWorkspaces == null ? base.getAllowedWorkspacePrefixes() : allowedWorkspaces,
                base.getAgentProfile()
        );
    }

    private List<String> splitList(String value) {
        if (value == null) {
            return null;
        }
        String v = value.trim();
        if (v.isEmpty()) {
            return List.of();
        }
        return Arrays.stream(v.split(","))
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .toList();
    }
}

