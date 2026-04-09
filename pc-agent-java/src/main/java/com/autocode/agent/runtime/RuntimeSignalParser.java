package com.autocode.agent.runtime;

import com.autocode.protocol.model.ServiceRuntimeDescriptor;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * Shared parser for runtime-related environment signals.
 */
public final class RuntimeSignalParser {

    private RuntimeSignalParser() {
    }

    public static List<ServiceRuntimeDescriptor.PortBinding> parsePortBindings(Map<String, String> env) {
        return parsePortBindings(readOptionalEnv(env, "MVP_RUNTIME_PORTS"));
    }

    /**
     * Parse {@code MVP_RUNTIME_PORTS} tokens separated by comma/semicolon.
     * Supported token shapes:
     * - {@code 8080}
     * - {@code http:8080}
     * - {@code http:8080:http}
     * - {@code 8080:http}
     */
    public static List<ServiceRuntimeDescriptor.PortBinding> parsePortBindings(String raw) {
        String value = trimToNull(raw);
        if (value == null) {
            return List.of();
        }
        ArrayList<ServiceRuntimeDescriptor.PortBinding> ports = new ArrayList<>();
        String[] entries = value.split("[,;]");
        int autoIndex = 1;
        for (String entryRaw : entries) {
            String entry = trimToNull(entryRaw);
            if (entry == null) {
                continue;
            }
            String[] parts = entry.split(":");
            ServiceRuntimeDescriptor.PortBinding binding = new ServiceRuntimeDescriptor.PortBinding();
            String name = null;
            String protocol = "http";
            Integer port = null;
            if (parts.length == 1) {
                port = parsePositivePort(parts[0]);
            } else if (parts.length == 2) {
                Integer firstPort = parsePositivePort(parts[0]);
                Integer secondPort = parsePositivePort(parts[1]);
                if (firstPort != null && secondPort == null) {
                    port = firstPort;
                    protocol = firstNonBlank(parts[1], "http");
                } else {
                    name = trimToNull(parts[0]);
                    port = secondPort;
                }
            } else {
                name = trimToNull(parts[0]);
                port = parsePositivePort(parts[1]);
                protocol = firstNonBlank(parts[2], "http");
            }
            if (port == null) {
                continue;
            }
            if (name == null) {
                name = "p" + autoIndex++;
            }
            binding.setName(name);
            binding.setPort(port);
            binding.setProtocol(protocol);
            ports.add(binding);
        }
        return ports.isEmpty() ? List.of() : List.copyOf(ports);
    }

    public static Integer resolvePrimaryRuntimePort(Map<String, String> env) {
        Integer single = parsePositivePort(readOptionalEnv(env, "MVP_RUNTIME_PORT"));
        if (single != null) {
            return single;
        }
        List<ServiceRuntimeDescriptor.PortBinding> ports = parsePortBindings(env);
        if (ports.isEmpty()) {
            return null;
        }
        return ports.get(0).getPort();
    }

    public static Integer parsePositivePort(String value) {
        String v = trimToNull(value);
        if (v == null) {
            return null;
        }
        try {
            int port = Integer.parseInt(v);
            if (port < 1 || port > 65535) {
                return null;
            }
            return port;
        } catch (NumberFormatException ex) {
            return null;
        }
    }

    public static String normalizeHealthPath(String path) {
        String value = trimToNull(path);
        if (value == null) {
            return null;
        }
        return value.startsWith("/") ? value : "/" + value;
    }

    private static String readOptionalEnv(Map<String, String> env, String key) {
        if (env == null || key == null) {
            return null;
        }
        return trimToNull(env.get(key));
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
}
