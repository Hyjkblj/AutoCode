/**
 * Node agent entrypoint for the MVP (register, poll tasks, execute, publish events).
 */
package com.autocode.agent;

import com.autocode.agent.config.AgentConfig;
import com.autocode.agent.runtime.AgentRunner;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

public class AgentApplication {

    public static void main(String[] args) throws Exception {
        loadDotEnv();
        AgentConfig config = AgentConfig.fromEnv();
        AgentRunner runner = new AgentRunner(config);
        runner.start();
    }

    /**
     * Loads key=value pairs from .env in the working directory into system properties
     * (as fallback for System.getenv). Does not override existing env vars.
     */
    private static void loadDotEnv() {
        Path envFile = Paths.get(".env");
        if (!Files.exists(envFile)) {
            return;
        }
        try {
            for (String line : Files.readAllLines(envFile)) {
                String trimmed = line.trim();
                if (trimmed.isEmpty() || trimmed.startsWith("#") || !trimmed.contains("=")) {
                    continue;
                }
                int idx = trimmed.indexOf('=');
                String key = trimmed.substring(0, idx).trim();
                String value = trimmed.substring(idx + 1).trim();
                // setdefault: only set if not already in env or system properties
                if (System.getenv(key) == null && System.getProperty(key) == null) {
                    System.setProperty(key, value);
                }
            }
        } catch (IOException e) {
            System.err.println("[AgentApplication] Failed to load .env: " + e.getMessage());
        }
    }
}
