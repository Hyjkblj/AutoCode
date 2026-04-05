package com.autocode.agent.sandbox;

import com.autocode.agent.client.AgentApiClient;
import com.autocode.agent.config.AgentConfig;
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

            HttpRequest invalidPostRequest = HttpRequest.newBuilder()
                    .uri(URI.create("http://127.0.0.1:" + port + "/sandbox/execute"))
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString("{}"))
                    .build();
            HttpResponse<String> invalidPostResponse = client.send(invalidPostRequest, HttpResponse.BodyHandlers.ofString());
            assertEquals(400, invalidPostResponse.statusCode());
            assertTrue(invalidPostResponse.body().contains("invalid_request"));
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
    }
}
