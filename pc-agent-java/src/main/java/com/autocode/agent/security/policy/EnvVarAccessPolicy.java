package com.autocode.agent.security.policy;

import com.autocode.agent.runtime.tool.ToolCall;
import com.autocode.agent.runtime.tool.ToolContext;

import java.util.LinkedHashSet;
import java.util.Locale;
import java.util.Set;

/**
 * Denies command invocations that reference sensitive environment variable names.
 */
public class EnvVarAccessPolicy implements ToolInvocationPolicy {
    private static final Set<String> DEFAULT_SENSITIVE_ENV_KEYS = Set.of(
            "MVP_AGENT_TOKEN",
            "MVP_OPERATOR_TOKEN",
            "MVP_JWT_SECRET",
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_SESSION_TOKEN",
            "GITHUB_TOKEN"
    );

    private final Set<String> sensitiveKeysLowerCase;

    public EnvVarAccessPolicy() {
        this(DEFAULT_SENSITIVE_ENV_KEYS);
    }

    public EnvVarAccessPolicy(Set<String> sensitiveKeys) {
        LinkedHashSet<String> normalized = new LinkedHashSet<>();
        if (sensitiveKeys != null) {
            for (String key : sensitiveKeys) {
                if (key == null) {
                    continue;
                }
                String k = key.trim().toLowerCase(Locale.ROOT);
                if (!k.isEmpty()) {
                    normalized.add(k);
                }
            }
        }
        this.sensitiveKeysLowerCase = normalized;
    }

    @Override
    public PolicyDecision evaluate(ToolCall call, ToolContext context) {
        if (sensitiveKeysLowerCase.isEmpty()) {
            return PolicyDecision.allow();
        }
        String command = readCommand(call);
        if (command == null) {
            return PolicyDecision.allow();
        }
        String normalized = command.toLowerCase(Locale.ROOT);
        for (String key : sensitiveKeysLowerCase) {
            if (normalized.contains(key)) {
                return PolicyDecision.deny("env_access_not_allowed");
            }
        }
        return PolicyDecision.allow();
    }

    private static String readCommand(ToolCall call) {
        if (call == null || call.getArgs() == null) {
            return null;
        }
        Object raw = call.getArgs().get("command");
        if (!(raw instanceof String s)) {
            return null;
        }
        return s;
    }
}
