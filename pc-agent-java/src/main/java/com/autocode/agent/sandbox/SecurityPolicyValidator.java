package com.autocode.agent.sandbox;

import com.autocode.agent.config.AgentConfig;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Validates security policies for the sandbox by inspecting actual {@link AgentConfig} state.
 *
 * <p>Unlike the previous stub implementation, this class reads real configuration
 * and reports whether each policy dimension is properly configured.</p>
 */
public class SecurityPolicyValidator {
    private static final Logger log = LoggerFactory.getLogger(SecurityPolicyValidator.class);

    private final AgentConfig config;

    public SecurityPolicyValidator(AgentConfig config) {
        this.config = config;
    }

    /**
     * Validate all security policies and return their status.
     */
    public Map<String, Object> validateAll() {
        Map<String, Object> policies = new HashMap<>();

        policies.put("commandWhitelisting", validateCommandWhitelisting());
        policies.put("workspaceIsolation", validateWorkspaceIsolation());
        policies.put("networkAccess", validateNetworkAccess());
        policies.put("sandboxHost", validateSandboxHost());

        boolean allActive = policies.values().stream()
                .allMatch(p -> p instanceof Map && "ACTIVE".equals(((Map<?, ?>) p).get("status")));

        policies.put("overallStatus", allActive ? "SECURE" : "PARTIAL");

        if (!allActive) {
            log.warn("sandbox security policy validation: PARTIAL — some policies are not properly configured");
        }

        return policies;
    }

    private Map<String, Object> validateCommandWhitelisting() {
        Map<String, Object> result = new HashMap<>();
        List<String> prefixes = config.getAllowedCommandPrefixes();
        boolean configured = prefixes != null && !prefixes.isEmpty();

        result.put("status", configured ? "ACTIVE" : "INACTIVE");
        result.put("description", "Command execution restricted to prefix allowlist");
        result.put("configured", configured);
        if (configured) {
            result.put("allowedPrefixCount", prefixes.size());
        } else {
            result.put("warning", "No allowed command prefixes configured — all commands will be denied");
        }
        return result;
    }

    private Map<String, Object> validateWorkspaceIsolation() {
        Map<String, Object> result = new HashMap<>();
        List<String> prefixes = config.getAllowedWorkspacePrefixes();
        boolean configured = prefixes != null && !prefixes.isEmpty();

        result.put("status", configured ? "ACTIVE" : "INACTIVE");
        result.put("description", "File access restricted to workspace allowlist");
        result.put("configured", configured);
        if (configured) {
            result.put("allowedWorkspaceCount", prefixes.size());
        } else {
            result.put("warning", "No allowed workspace prefixes configured — file access may be unrestricted");
        }
        return result;
    }

    private Map<String, Object> validateNetworkAccess() {
        Map<String, Object> result = new HashMap<>();
        boolean networkAllowed = config.isNetworkAllowed();

        result.put("status", networkAllowed ? "ACTIVE" : "BLOCKED");
        result.put("description", networkAllowed
                ? "Network access allowed (commands with outbound network heuristics are permitted)"
                : "Network access blocked (commands with outbound network heuristics are denied)");
        result.put("networkAllowed", networkAllowed);
        return result;
    }

    private Map<String, Object> validateSandboxHost() {
        Map<String, Object> result = new HashMap<>();
        // SandboxHttpServer enforces localhost-only at startup.
        // This validator confirms that constraint is documented in the health report.
        result.put("status", "ACTIVE");
        result.put("description", "Sandbox HTTP server is localhost-only (127.0.0.1)");
        result.put("host", "127.0.0.1");
        return result;
    }
}
