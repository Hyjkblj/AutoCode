package com.autocode.agent.sandbox;

import com.autocode.agent.client.AgentApiClient;
import com.autocode.agent.config.AgentConfig;
import com.autocode.protocol.model.ApprovalDecision;
import com.autocode.protocol.model.TaskEvent;
import org.junit.jupiter.api.Test;

import java.net.ServerSocket;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class SandboxHttpServerTest {

    @Test
    void constructorRejectsNonLoopbackHost() throws Exception {
        Path workspace = Files.createTempDirectory("sandbox-http-host");
        SandboxExecutionService service = new SandboxExecutionService(new NoopAgentApiClient(), configWithWorkspace(workspace));

        try {
            new SandboxHttpServer("0.0.0.0", 18080, service);
        } catch (IllegalArgumentException ex) {
            assertTrue(ex.getMessage().contains("127.0.0.1"));
            return;
        }
        throw new AssertionError("expected IllegalArgumentException");
    }

    @Test
    void httpServerReturns405And400ForInvalidRequests() throws Exception {
        Path workspace = Files.createTempDirectory("sandbox-http");
        SandboxExecutionService service = new SandboxExecutionService(new NoopAgentApiClient(), configWithWorkspace(workspace));
        int port = findAvailablePort();
        SandboxHttpServer server = new SandboxHttpServer("127.0.0.1", port, service);

        server.start();
        try {
            HttpClient client = HttpClient.newHttpClient();

            HttpRequest healthRequest = HttpRequest.newBuilder()
                    .uri(URI.create("http://127.0.0.1:" + port + "/sandbox/health"))
                    .GET()
                    .build();
            HttpResponse<String> healthResponse = client.send(healthRequest, HttpResponse.BodyHandlers.ofString());
            assertEquals(200, healthResponse.statusCode());
            assertTrue(healthResponse.body().contains("\"status\":\"up\""));

            HttpRequest badMethodRequest = HttpRequest.newBuilder()
                    .uri(URI.create("http://127.0.0.1:" + port + "/sandbox/execute"))
                    .GET()
                    .build();
            HttpResponse<String> badMethodResponse = client.send(badMethodRequest, HttpResponse.BodyHandlers.ofString());
            assertEquals(405, badMethodResponse.statusCode());
            assertTrue(badMethodResponse.body().contains("method_not_allowed"));
            assertTrue(badMethodResponse.body().contains("\"status\":\"method_not_allowed\""));

            HttpRequest invalidPostRequest = HttpRequest.newBuilder()
                    .uri(URI.create("http://127.0.0.1:" + port + "/sandbox/execute"))
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString("{}"))
                    .build();
            HttpResponse<String> invalidPostResponse = client.send(invalidPostRequest, HttpResponse.BodyHandlers.ofString());
            assertEquals(400, invalidPostResponse.statusCode());
            assertTrue(invalidPostResponse.body().contains("invalid_request"));
            assertTrue(invalidPostResponse.body().contains("\"error\":\"taskId is required\""));

            HttpRequest malformedJsonRequest = HttpRequest.newBuilder()
                    .uri(URI.create("http://127.0.0.1:" + port + "/sandbox/execute"))
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString("{"))
                    .build();
            HttpResponse<String> malformedJsonResponse = client.send(malformedJsonRequest, HttpResponse.BodyHandlers.ofString());
            assertEquals(400, malformedJsonResponse.statusCode());
            assertTrue(malformedJsonResponse.body().contains("\"status\":\"invalid_request\""));
            assertTrue(malformedJsonResponse.body().contains("\"error\":\"invalid_json\""));
        } finally {
            server.stop();
        }
    }

    @Test
    void httpServerExecuteReturns200ForValidRequest() throws Exception {
        Path workspace = Files.createTempDirectory("sandbox-http-ok");
        SandboxExecutionService service = new SandboxExecutionService(new NoopAgentApiClient(), configWithWorkspace(workspace));
        int port = findAvailablePort();
        SandboxHttpServer server = new SandboxHttpServer("127.0.0.1", port, service);

        server.start();
        try {
            HttpClient client = HttpClient.newHttpClient();
            String cwd = workspace.toString().replace("\\", "\\\\");
            String requestJson = "{"
                    + "\"taskId\":\"task_http_ok\","
                    + "\"command\":\"echo sandbox_http_ok\","
                    + "\"cwd\":\"" + cwd + "\","
                    + "\"assistant\":\"python-agent\","
                    + "\"sessionId\":\"sess_http_ok\""
                    + "}";

            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create("http://127.0.0.1:" + port + "/sandbox/execute"))
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(requestJson))
                    .build();
            HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());

            assertEquals(200, response.statusCode());
            assertTrue(response.body().contains("\"ok\":true"));
            assertTrue(response.body().contains("\"status\":\"ok\""));
            assertTrue(response.body().contains("\"tool\":\"command.exec\""));
        } finally {
            server.stop();
        }
    }

    private static int findAvailablePort() throws Exception {
        try (ServerSocket socket = new ServerSocket(0)) {
            socket.setReuseAddress(true);
            return socket.getLocalPort();
        }
    }

    private static AgentConfig configWithWorkspace(Path workspacePrefix) {
        return new AgentConfig(
                "http://localhost:8048",
                "node-sandbox-test",
                "agent-test-token",
                200,
                500,
                1,
                List.of("echo"),
                List.of(workspacePrefix.toString()),
                "coder",
                true);
    }

    private static final class NoopAgentApiClient extends AgentApiClient {
        private NoopAgentApiClient() {
            super("http://localhost:8048", "sandbox-token");
        }

        @Override
        public void publishEvent(String taskId, TaskEvent event) {
            // no-op for local unit tests
        }

        @Override
        public ApprovalDecision getApprovalDecision(String taskId) {
            return ApprovalDecision.APPROVE;
        }
    }
}
