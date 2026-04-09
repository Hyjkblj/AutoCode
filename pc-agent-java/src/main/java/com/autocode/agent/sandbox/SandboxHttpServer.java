package com.autocode.agent.sandbox;

import com.autocode.agent.client.AgentApiClient;
import com.autocode.agent.config.AgentConfig;
import com.autocode.protocol.model.SandboxErrorResponse;
import com.autocode.protocol.model.SandboxExecuteRequest;
import com.autocode.protocol.model.SandboxExecuteResponse;
import com.autocode.protocol.model.SandboxHealthResponse;
import com.autocode.protocol.model.SandboxToolsResponse;
import com.autocode.protocol.validation.ContractViolationException;
import com.autocode.protocol.validation.SandboxExecuteContractValidator;
import com.autocode.protocol.validation.SandboxHttpContractValidator;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import com.sun.net.httpserver.HttpServer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.util.Objects;

/**
 * Lightweight localhost-only sandbox execute endpoint for Python agent calls.
 */
public class SandboxHttpServer {
    private static final Logger log = LoggerFactory.getLogger(SandboxHttpServer.class);

    private static final String ENV_ENABLED = "MVP_SANDBOX_SERVER_ENABLED";
    private static final String ENV_HOST = "MVP_SANDBOX_HOST";
    private static final String ENV_PORT = "MVP_SANDBOX_PORT";
    private static final String LOCALHOST = "127.0.0.1";

    private final String host;
    private final int port;
    private final SandboxExecutionService service;
    private final ObjectMapper objectMapper = new ObjectMapper().findAndRegisterModules();
    private HttpServer server;

    public SandboxHttpServer(String host, int port, SandboxExecutionService service) {
        String normalizedHost = readHost(host, LOCALHOST);
        if (!LOCALHOST.equals(normalizedHost)) {
            throw new IllegalArgumentException("sandbox host must be 127.0.0.1");
        }
        this.host = normalizedHost;
        this.port = port;
        this.service = Objects.requireNonNull(service, "service");
    }

    public static boolean isEnabledFromEnv() {
        String raw = System.getenv(ENV_ENABLED);
        if (raw == null || raw.isBlank()) {
            return false;
        }
        String normalized = raw.trim().toLowerCase();
        return normalized.equals("1") || normalized.equals("true") || normalized.equals("yes") || normalized.equals("on");
    }

    public static SandboxHttpServer fromEnv(AgentApiClient apiClient, AgentConfig config) {
        String requestedHost = readHost(System.getenv(ENV_HOST), LOCALHOST);
        String host = LOCALHOST;
        if (!LOCALHOST.equals(requestedHost)) {
            log.warn("{}={} ignored; sandbox server is localhost-only (127.0.0.1)", ENV_HOST, requestedHost);
        }
        int port = parsePort(readEnv(ENV_PORT, "18080"), 18080);
        return new SandboxHttpServer(host, port, new SandboxExecutionService(apiClient, config));
    }

    public synchronized void start() throws IOException {
        if (server != null) {
            return;
        }
        InetSocketAddress address = new InetSocketAddress(host, port);
        HttpServer httpServer = HttpServer.create(address, 0);
        httpServer.createContext("/sandbox/execute", new ExecuteHandler());
        httpServer.createContext("/sandbox/tools", exchange -> {
            if (!"GET".equalsIgnoreCase(exchange.getRequestMethod())) {
                writeError(exchange, 405, "method_not_allowed", "method_not_allowed");
                return;
            }
            SandboxToolsResponse response = SandboxToolsResponse.of(service.listToolManifests());
            SandboxHttpContractValidator.validateToolsResponse(response);
            writeJson(exchange, 200, response);
        });
        httpServer.createContext("/sandbox/health", exchange -> {
            if (!"GET".equalsIgnoreCase(exchange.getRequestMethod())) {
                writeError(exchange, 405, "method_not_allowed", "method_not_allowed");
                return;
            }
            SandboxHealthResponse response = SandboxHealthResponse.up();
            SandboxHttpContractValidator.validateHealthResponse(response);
            writeJson(exchange, 200, response);
        });
        httpServer.start();
        server = httpServer;
        log.info("Sandbox HTTP server started on {}:{}", host, port);
    }

    public synchronized void stop() {
        if (server != null) {
            server.stop(0);
            server = null;
            log.info("Sandbox HTTP server stopped");
        }
    }

    private final class ExecuteHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            if (!"POST".equalsIgnoreCase(exchange.getRequestMethod())) {
                writeError(exchange, 405, "method_not_allowed", "method_not_allowed");
                return;
            }
            try {
                byte[] bodyBytes = exchange.getRequestBody().readAllBytes();
                SandboxExecuteRequest request = objectMapper.readValue(bodyBytes, SandboxExecuteRequest.class);
                SandboxExecuteResponse response = service.execute(request);
                SandboxExecuteContractValidator.validateResponse(response);
                writeJson(exchange, 200, response);
            } catch (JsonProcessingException ex) {
                writeError(exchange, 400, "invalid_request", "invalid_json");
            } catch (IllegalArgumentException ex) {
                writeError(exchange, 400, "invalid_request", ex.getMessage());
            } catch (ContractViolationException ex) {
                writeError(exchange, 500, "contract_violation", ex.getMessage());
            } catch (InterruptedException ex) {
                Thread.currentThread().interrupt();
                writeError(exchange, 503, "interrupted", "sandbox_interrupted");
            } catch (Exception ex) {
                log.warn("Sandbox execute failed: {}", ex.getMessage());
                writeError(exchange, 500, "error", ex.getMessage() == null ? "sandbox_error" : ex.getMessage());
            }
        }
    }

    private void writeError(HttpExchange exchange, int statusCode, String status, String error) throws IOException {
        SandboxErrorResponse response = SandboxErrorResponse.of(status, error);
        SandboxHttpContractValidator.validateErrorResponse(response);
        writeJson(exchange, statusCode, response);
    }

    private void writeJson(HttpExchange exchange, int statusCode, Object payload) throws IOException {
        byte[] bytes = objectMapper.writeValueAsBytes(payload);
        exchange.getResponseHeaders().set("Content-Type", "application/json; charset=utf-8");
        exchange.sendResponseHeaders(statusCode, bytes.length);
        exchange.getResponseBody().write(bytes);
        exchange.getResponseBody().close();
    }

    private static String readEnv(String key, String fallback) {
        String value = System.getenv(key);
        if (value == null || value.isBlank()) {
            return fallback;
        }
        return value.trim();
    }

    private static String readHost(String value, String fallback) {
        if (value == null || value.isBlank()) {
            return fallback;
        }
        return value.trim();
    }

    private static int parsePort(String value, int fallback) {
        try {
            int port = Integer.parseInt(value);
            return (port > 0 && port <= 65535) ? port : fallback;
        } catch (NumberFormatException ignored) {
            return fallback;
        }
    }
}
