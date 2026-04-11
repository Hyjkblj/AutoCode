/**
 * Agent runtime configuration loaded from environment variables.
 */
package com.autocode.agent.config;

import java.util.Arrays;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Properties;

public class AgentConfig {

    private static final String DEFAULT_AGENT_VERSION = "0.1.0";
    private static final String DEFAULT_INTENT_TOOL = "command.exec";
    private static final String DEFAULT_INTENT_ACTION = "run_command";

    /**
     * OkHttp timeouts for control-plane calls. Defaults match the previous hard-coded client behavior.
     * <p>
     * Env: {@code MVP_HTTP_CONNECT_TIMEOUT_SECONDS}, {@code MVP_HTTP_READ_TIMEOUT_SECONDS},
     * {@code MVP_HTTP_WRITE_TIMEOUT_SECONDS}, {@code MVP_HTTP_CALL_TIMEOUT_SECONDS} (all optional).
     */
    public static final class HttpTimeouts {
        public static final HttpTimeouts DEFAULTS = new HttpTimeouts(15, 120, 60, 180);

        private final long connectSeconds;
        private final long readSeconds;
        private final long writeSeconds;
        private final long callSeconds;

        private HttpTimeouts(long connectSeconds, long readSeconds, long writeSeconds, long callSeconds) {
            this.connectSeconds = connectSeconds;
            this.readSeconds = readSeconds;
            this.writeSeconds = writeSeconds;
            this.callSeconds = callSeconds;
        }

        public static HttpTimeouts fromEnv() {
            return new HttpTimeouts(
                    parsePositiveSeconds("MVP_HTTP_CONNECT_TIMEOUT_SECONDS", "15", 15),
                    parsePositiveSeconds("MVP_HTTP_READ_TIMEOUT_SECONDS", "120", 120),
                    parsePositiveSeconds("MVP_HTTP_WRITE_TIMEOUT_SECONDS", "60", 60),
                    parsePositiveSeconds("MVP_HTTP_CALL_TIMEOUT_SECONDS", "180", 180));
        }

        /**
         * Override timeouts from a {@code .properties} file (same keys as env). Unset keys keep {@code base} values.
         */
        public static HttpTimeouts mergeFromProperties(HttpTimeouts base, Properties props) {
            if (props == null) {
                return base != null ? base : DEFAULTS;
            }
            HttpTimeouts b = base != null ? base : DEFAULTS;
            return new HttpTimeouts(
                    parsePropertySeconds(props, "MVP_HTTP_CONNECT_TIMEOUT_SECONDS", b.connectSeconds),
                    parsePropertySeconds(props, "MVP_HTTP_READ_TIMEOUT_SECONDS", b.readSeconds),
                    parsePropertySeconds(props, "MVP_HTTP_WRITE_TIMEOUT_SECONDS", b.writeSeconds),
                    parsePropertySeconds(props, "MVP_HTTP_CALL_TIMEOUT_SECONDS", b.callSeconds));
        }

        private static long parsePropertySeconds(Properties props, String key, long fallback) {
            String raw = props.getProperty(key);
            if (raw == null || raw.isBlank()) {
                return fallback;
            }
            try {
                long v = Long.parseLong(raw.trim());
                return v > 0 ? v : fallback;
            } catch (NumberFormatException e) {
                return fallback;
            }
        }

        private static long parsePositiveSeconds(String key, String defaultStr, long fallback) {
            try {
                long v = Long.parseLong(readEnv(key, defaultStr).trim());
                return v > 0 ? v : fallback;
            } catch (NumberFormatException e) {
                return fallback;
            }
        }

        private static String readEnv(String key, String fallback) {
            String value = System.getenv(key);
            if (value == null || value.isBlank()) {
                return fallback;
            }
            return value;
        }

        public long getConnectSeconds() {
            return connectSeconds;
        }

        public long getReadSeconds() {
            return readSeconds;
        }

        public long getWriteSeconds() {
            return writeSeconds;
        }

        public long getCallSeconds() {
            return callSeconds;
        }
    }

    /**
     * Optional client certificate + trust material for HTTPS/mTLS to the control plane.
     * <p>
     * Env: {@code MVP_AGENT_TLS_KEYSTORE_PATH} (when set, client cert is sent). Optional:
     * {@code MVP_AGENT_TLS_KEYSTORE_PASSWORD}, {@code MVP_AGENT_TLS_KEYSTORE_TYPE} (default PKCS12),
     * {@code MVP_AGENT_TLS_TRUSTSTORE_PATH}, {@code MVP_AGENT_TLS_TRUSTSTORE_PASSWORD},
     * {@code MVP_AGENT_TLS_TRUSTSTORE_TYPE} (default JKS).
     */
    public static final class ClientTls {
        public static final ClientTls DISABLED = new ClientTls(null, "", "PKCS12", null, "", "JKS");

        private final String keyStorePath;
        private final String keyStorePassword;
        private final String keyStoreType;
        private final String trustStorePath;
        private final String trustStorePassword;
        private final String trustStoreType;

        private ClientTls(
                String keyStorePath,
                String keyStorePassword,
                String keyStoreType,
                String trustStorePath,
                String trustStorePassword,
                String trustStoreType) {
            this.keyStorePath = keyStorePath;
            this.keyStorePassword = keyStorePassword != null ? keyStorePassword : "";
            this.keyStoreType = (keyStoreType == null || keyStoreType.isBlank()) ? "PKCS12" : keyStoreType.trim();
            this.trustStorePath = trustStorePath;
            this.trustStorePassword = trustStorePassword != null ? trustStorePassword : "";
            this.trustStoreType = (trustStoreType == null || trustStoreType.isBlank()) ? "JKS" : trustStoreType.trim();
        }

        public static ClientTls disabled() {
            return DISABLED;
        }

        public static ClientTls fromEnv() {
            String ks = readEnv("MVP_AGENT_TLS_KEYSTORE_PATH", "");
            String trust = readEnv("MVP_AGENT_TLS_TRUSTSTORE_PATH", "");
            String keyPath = (ks == null || ks.isBlank()) ? null : ks.trim();
            String trustPath = (trust == null || trust.isBlank()) ? null : trust.trim();
            if (keyPath == null && trustPath == null) {
                return DISABLED;
            }
            return new ClientTls(
                    keyPath,
                    readEnv("MVP_AGENT_TLS_KEYSTORE_PASSWORD", ""),
                    readEnv("MVP_AGENT_TLS_KEYSTORE_TYPE", "PKCS12"),
                    trustPath,
                    readEnv("MVP_AGENT_TLS_TRUSTSTORE_PASSWORD", ""),
                    readEnv("MVP_AGENT_TLS_TRUSTSTORE_TYPE", "JKS"));
        }

        /**
         * Override TLS settings from a {@code .properties} file (same keys as env). Unset keys keep {@code base} values.
         * Blank {@code MVP_AGENT_TLS_KEYSTORE_PATH} disables client-certificate key material while still allowing a
         * truststore-only TLS configuration.
         */
        public static ClientTls mergeFromProperties(ClientTls base, Properties props) {
            ClientTls b = base != null ? base : DISABLED;
            if (props == null) {
                return b;
            }

            String keyStorePath = overridePath(props, "MVP_AGENT_TLS_KEYSTORE_PATH", b.keyStorePath);
            String trustStorePath = overridePath(props, "MVP_AGENT_TLS_TRUSTSTORE_PATH", b.trustStorePath);
            if ((keyStorePath == null || keyStorePath.isBlank())
                    && (trustStorePath == null || trustStorePath.isBlank())) {
                return DISABLED;
            }

            return new ClientTls(
                    keyStorePath,
                    overrideText(props, "MVP_AGENT_TLS_KEYSTORE_PASSWORD", b.keyStorePassword),
                    overrideText(props, "MVP_AGENT_TLS_KEYSTORE_TYPE", b.keyStoreType),
                    trustStorePath,
                    overrideText(props, "MVP_AGENT_TLS_TRUSTSTORE_PASSWORD", b.trustStorePassword),
                    overrideText(props, "MVP_AGENT_TLS_TRUSTSTORE_TYPE", b.trustStoreType));
        }

        private static String overridePath(Properties props, String key, String fallback) {
            String raw = props.getProperty(key);
            if (raw == null) {
                return fallback;
            }
            String trimmed = raw.trim();
            return trimmed.isEmpty() ? null : trimmed;
        }

        private static String overrideText(Properties props, String key, String fallback) {
            String raw = props.getProperty(key);
            if (raw == null) {
                return fallback;
            }
            return raw;
        }

        private static String readEnv(String key, String fallback) {
            String value = System.getenv(key);
            if (value == null) {
                return fallback;
            }
            return value;
        }

        public boolean isKeyMaterialConfigured() {
            return keyStorePath != null && !keyStorePath.isBlank();
        }

        public boolean isTrustMaterialConfigured() {
            return trustStorePath != null && !trustStorePath.isBlank();
        }

        public boolean isTlsConfigured() {
            return isKeyMaterialConfigured() || isTrustMaterialConfigured();
        }

        public String getKeyStorePath() {
            return keyStorePath;
        }

        public String getKeyStorePassword() {
            return keyStorePassword;
        }

        public String getKeyStoreType() {
            return keyStoreType;
        }

        public String getTrustStorePath() {
            return trustStorePath;
        }

        public String getTrustStorePassword() {
            return trustStorePassword;
        }

        public String getTrustStoreType() {
            return trustStoreType;
        }
    }

    /**
     * Rule-based intent routing entry loaded from {@code MVP_INTENT_RULES}.
     * <p>
     * Rule format (semicolon-separated): {@code profile=<p>|skill=<s>} or
     * {@code keywords=<k1,k2>|skill=<s>} with optional {@code tool/action/command}.
     */
    public record IntentRule(
            String profile,
            List<String> keywords,
            String skill,
            String tool,
            String action,
            String command) {

        public IntentRule {
            profile = normalizeProfile(profile);
            keywords = normalizeKeywords(keywords);
            skill = firstNonBlank(skill, DEFAULT_INTENT_TOOL);
            tool = firstNonBlank(tool, DEFAULT_INTENT_TOOL);
            action = firstNonBlank(action, DEFAULT_INTENT_ACTION);
            command = trimToNull(command);
        }

        public boolean matchesProfile(String candidate) {
            String normalized = normalizeProfile(candidate);
            return profile != null && profile.equals(normalized);
        }

        public String firstMatchedKeyword(String promptLowerCase) {
            if (promptLowerCase == null || promptLowerCase.isBlank() || keywords.isEmpty()) {
                return null;
            }
            for (String keyword : keywords) {
                if (promptLowerCase.contains(keyword)) {
                    return keyword;
                }
            }
            return null;
        }
    }

    private final String baseUrl;
    private final String nodeId;
    private final String agentToken;
    private final long pollIntervalMs;
    private final long heartbeatIntervalMs;
    private final long approvalTimeoutSeconds;
    private final List<String> allowedCommandPrefixes;
    private final List<String> allowedWorkspacePrefixes;
    private final String agentProfile;
    private final boolean networkAllowed;
    private final HttpTimeouts httpTimeouts;
    private final ClientTls clientTls;
    /** Reported to control plane on register; override with {@code MVP_AGENT_VERSION}. */
    private final String agentVersion;
    private final List<IntentRule> intentRules;

    /**
     * Preserves previous behavior: {@code networkAllowed == true} (prefix allowlist only).
     */
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
        this(
                baseUrl,
                nodeId,
                agentToken,
                pollIntervalMs,
                heartbeatIntervalMs,
                approvalTimeoutSeconds,
                allowedCommandPrefixes,
                allowedWorkspacePrefixes,
                agentProfile,
                true
        );
    }

    public AgentConfig(
            String baseUrl,
            String nodeId,
            String agentToken,
            long pollIntervalMs,
            long heartbeatIntervalMs,
            long approvalTimeoutSeconds,
            List<String> allowedCommandPrefixes,
            List<String> allowedWorkspacePrefixes,
            String agentProfile,
            boolean networkAllowed
    ) {
        this(
                baseUrl,
                nodeId,
                agentToken,
                pollIntervalMs,
                heartbeatIntervalMs,
                approvalTimeoutSeconds,
                allowedCommandPrefixes,
                allowedWorkspacePrefixes,
                agentProfile,
                networkAllowed,
                HttpTimeouts.DEFAULTS,
                ClientTls.DISABLED,
                DEFAULT_AGENT_VERSION);
    }

    public AgentConfig(
            String baseUrl,
            String nodeId,
            String agentToken,
            long pollIntervalMs,
            long heartbeatIntervalMs,
            long approvalTimeoutSeconds,
            List<String> allowedCommandPrefixes,
            List<String> allowedWorkspacePrefixes,
            String agentProfile,
            boolean networkAllowed,
            HttpTimeouts httpTimeouts
    ) {
        this(
                baseUrl,
                nodeId,
                agentToken,
                pollIntervalMs,
                heartbeatIntervalMs,
                approvalTimeoutSeconds,
                allowedCommandPrefixes,
                allowedWorkspacePrefixes,
                agentProfile,
                networkAllowed,
                httpTimeouts,
                ClientTls.DISABLED,
                DEFAULT_AGENT_VERSION);
    }

    public AgentConfig(
            String baseUrl,
            String nodeId,
            String agentToken,
            long pollIntervalMs,
            long heartbeatIntervalMs,
            long approvalTimeoutSeconds,
            List<String> allowedCommandPrefixes,
            List<String> allowedWorkspacePrefixes,
            String agentProfile,
            boolean networkAllowed,
            HttpTimeouts httpTimeouts,
            ClientTls clientTls
    ) {
        this(
                baseUrl,
                nodeId,
                agentToken,
                pollIntervalMs,
                heartbeatIntervalMs,
                approvalTimeoutSeconds,
                allowedCommandPrefixes,
                allowedWorkspacePrefixes,
                agentProfile,
                networkAllowed,
                httpTimeouts,
                clientTls,
                DEFAULT_AGENT_VERSION);
    }

    public AgentConfig(
            String baseUrl,
            String nodeId,
            String agentToken,
            long pollIntervalMs,
            long heartbeatIntervalMs,
            long approvalTimeoutSeconds,
            List<String> allowedCommandPrefixes,
            List<String> allowedWorkspacePrefixes,
            String agentProfile,
            boolean networkAllowed,
            HttpTimeouts httpTimeouts,
            ClientTls clientTls,
            String agentVersion
    ) {
        this(
                baseUrl,
                nodeId,
                agentToken,
                pollIntervalMs,
                heartbeatIntervalMs,
                approvalTimeoutSeconds,
                allowedCommandPrefixes,
                allowedWorkspacePrefixes,
                agentProfile,
                networkAllowed,
                httpTimeouts,
                clientTls,
                agentVersion,
                List.of());
    }

    public AgentConfig(
            String baseUrl,
            String nodeId,
            String agentToken,
            long pollIntervalMs,
            long heartbeatIntervalMs,
            long approvalTimeoutSeconds,
            List<String> allowedCommandPrefixes,
            List<String> allowedWorkspacePrefixes,
            String agentProfile,
            boolean networkAllowed,
            HttpTimeouts httpTimeouts,
            ClientTls clientTls,
            String agentVersion,
            List<IntentRule> intentRules
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
        this.networkAllowed = networkAllowed;
        this.httpTimeouts = httpTimeouts != null ? httpTimeouts : HttpTimeouts.DEFAULTS;
        this.clientTls = clientTls != null ? clientTls : ClientTls.DISABLED;
        String v = agentVersion == null ? "" : agentVersion.trim();
        this.agentVersion = v.isBlank() ? DEFAULT_AGENT_VERSION : v;
        this.intentRules = intentRules == null ? List.of() : List.copyOf(intentRules);
    }

    public static AgentConfig fromEnv() {
        String baseUrl = read("MVP_BASE_URL", "http://localhost:8058");
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
        boolean networkAllowed = truthyEnv("MVP_NETWORK_ALLOWED", true);
        String agentVersion = read("MVP_AGENT_VERSION", DEFAULT_AGENT_VERSION).trim();
        if (agentVersion.isBlank()) {
            agentVersion = DEFAULT_AGENT_VERSION;
        }
        List<IntentRule> intentRules = parseIntentRules(read("MVP_INTENT_RULES", ""));
        return new AgentConfig(
                baseUrl,
                nodeId,
                agentToken,
                pollInterval,
                heartbeatInterval,
                approvalTimeout,
                allowedCommands,
                allowedWorkspaces,
                agentProfile,
                networkAllowed,
                HttpTimeouts.fromEnv(),
                ClientTls.fromEnv(),
                agentVersion,
                intentRules
        );
    }

    public static List<IntentRule> parseIntentRules(String raw) {
        String value = trimToNull(raw);
        if (value == null) {
            return List.of();
        }
        ArrayList<IntentRule> rules = new ArrayList<>();
        for (String ruleRaw : value.split(";")) {
            String spec = trimToNull(ruleRaw);
            if (spec == null) {
                continue;
            }
            Map<String, String> kv = parseIntentRuleSegments(spec);
            String profile = kv.get("profile");
            List<String> keywords = splitCsv(firstNonBlank(kv.get("keyword"), kv.get("keywords")));
            if (profile == null && keywords.isEmpty()) {
                continue;
            }
            rules.add(new IntentRule(
                    profile,
                    keywords,
                    firstNonBlank(kv.get("skill"), kv.get("intent"), kv.get("target")),
                    kv.get("tool"),
                    kv.get("action"),
                    kv.get("command")));
        }
        return rules.isEmpty() ? List.of() : List.copyOf(rules);
    }

    private static Map<String, String> parseIntentRuleSegments(String spec) {
        HashMap<String, String> kv = new HashMap<>();
        for (String tokenRaw : spec.split("\\|")) {
            String token = trimToNull(tokenRaw);
            if (token == null) {
                continue;
            }
            int split = token.indexOf('=');
            if (split <= 0) {
                continue;
            }
            String key = token.substring(0, split).trim().toLowerCase(Locale.ROOT);
            String val = token.substring(split + 1).trim();
            if (!key.isEmpty()) {
                kv.put(key, val);
            }
        }
        return kv;
    }

    private static List<String> splitCsv(String raw) {
        String value = trimToNull(raw);
        if (value == null) {
            return List.of();
        }
        ArrayList<String> parts = new ArrayList<>();
        for (String p : value.split(",")) {
            String normalized = normalizeKeyword(p);
            if (normalized != null) {
                parts.add(normalized);
            }
        }
        return parts.isEmpty() ? List.of() : List.copyOf(parts);
    }

    private static String read(String key, String fallback) {
        String value = System.getenv(key);
        if (value == null || value.isBlank()) {
            value = System.getProperty(key);
        }
        if (value == null || value.isBlank()) {
            return fallback;
        }
        return value;
    }

    private static boolean truthyEnv(String key, boolean defaultValue) {
        String value = System.getenv(key);
        if (value == null || value.isBlank()) {
            return defaultValue;
        }
        String v = value.trim().toLowerCase();
        return v.equals("1") || v.equals("true") || v.equals("yes") || v.equals("on");
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

    /**
     * When false, commands whose text matches outbound-network heuristics are denied even if on the prefix allowlist
     * (same idea as Python runner {@code AUTOCODE_NETWORK_ALLOWED}).
     */
    public boolean isNetworkAllowed() {
        return networkAllowed;
    }

    public HttpTimeouts getHttpTimeouts() {
        return httpTimeouts;
    }

    public ClientTls getClientTls() {
        return clientTls;
    }

    public String getAgentVersion() {
        return agentVersion;
    }

    public List<IntentRule> getIntentRules() {
        return intentRules;
    }

    private static String trimToNull(String value) {
        if (value == null) {
            return null;
        }
        String trimmed = value.trim();
        return trimmed.isEmpty() ? null : trimmed;
    }

    private static String firstNonBlank(String... values) {
        if (values == null) {
            return null;
        }
        for (String value : values) {
            String normalized = trimToNull(value);
            if (normalized != null) {
                return normalized;
            }
        }
        return null;
    }

    private static String normalizeProfile(String value) {
        String normalized = trimToNull(value);
        return normalized == null ? null : normalized.toLowerCase(Locale.ROOT);
    }

    private static String normalizeKeyword(String value) {
        String normalized = trimToNull(value);
        return normalized == null ? null : normalized.toLowerCase(Locale.ROOT);
    }

    private static List<String> normalizeKeywords(List<String> keywords) {
        if (keywords == null || keywords.isEmpty()) {
            return List.of();
        }
        ArrayList<String> normalized = new ArrayList<>();
        for (String keyword : keywords) {
            String value = normalizeKeyword(keyword);
            if (value != null) {
                normalized.add(value);
            }
        }
        return normalized.isEmpty() ? List.of() : List.copyOf(normalized);
    }
}
