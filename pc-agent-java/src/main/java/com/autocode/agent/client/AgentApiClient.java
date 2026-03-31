/**
 * HTTP client for the control plane agent endpoints (register/heartbeat/poll/publish events).
 */
package com.autocode.agent.client;

import com.autocode.protocol.model.ApprovalDecision;
import com.autocode.protocol.model.TaskEvent;
import com.autocode.protocol.model.TaskSummary;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import okhttp3.HttpUrl;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

import java.io.IOException;
import java.util.Map;
import java.util.Optional;

public class AgentApiClient {
    private static final MediaType JSON = MediaType.get("application/json; charset=utf-8");

    private final OkHttpClient httpClient = new OkHttpClient();
    private final ObjectMapper objectMapper;
    private final String baseUrl;
    private final String agentToken;

    public AgentApiClient(String baseUrl, String agentToken) {
        this.baseUrl = baseUrl;
        this.agentToken = agentToken;
        this.objectMapper = new ObjectMapper();
        this.objectMapper.registerModule(new JavaTimeModule());
    }

    /**
     * 注册节点到控制平面（用于可见性与在线状态管理）。
     */
    public void register(String nodeId) throws IOException {
        String profile = System.getenv().getOrDefault("MVP_AGENT_PROFILE", "coder");
        Map<String, Object> body = Map.of(
                "nodeId", nodeId,
                "version", "0.1.0",
                "capabilities", "codex,events,approval,profile:" + profile
        );
        Request request = post("/api/v1/agent/register", body);
        executeNoPayload(request);
    }

    /**
     * 节点心跳（控制平面用来判断 online/offline）。
     */
    public void heartbeat(String nodeId) throws IOException {
        Request request = post("/api/v1/agent/heartbeat", Map.of("nodeId", nodeId));
        executeNoPayload(request);
    }

    /**
     * 轮询领取下一条任务（服务端可能返回 204 表示暂无任务）。
     */
    public Optional<TaskSummary> pollNextTask(String nodeId) throws IOException {
        String profile = System.getenv().getOrDefault("MVP_AGENT_PROFILE", "coder");
        HttpUrl url = HttpUrl.parse(baseUrl + "/api/v1/agent/tasks/next")
                .newBuilder()
                .addQueryParameter("nodeId", nodeId)
                .addQueryParameter("profile", profile)
                .build();

        Request request = new Request.Builder()
                .url(url)
                .header("X-Agent-Token", agentToken)
                .get()
                .build();

        try (Response response = httpClient.newCall(request).execute()) {
            if (response.code() == 204) {
                return Optional.empty();
            }
            if (!response.isSuccessful()) {
                throw new IOException("poll task failed: " + response.code());
            }
            String body = response.body().string();
            ApiResponse<TaskSummary> apiResponse = objectMapper.readValue(body, new TypeReference<ApiResponse<TaskSummary>>() {
            });
            return Optional.ofNullable(apiResponse.getPayload());
        }
    }

    /**
     * 上报任务事件（控制平面会落库、更新状态机，并通过 WS 广播）。
     */
    public void publishEvent(String taskId, TaskEvent event) throws IOException {
        Request request = post("/api/v1/agent/tasks/" + taskId + "/events", Map.of("event", event));
        executeNoPayload(request);
    }

    /**
     * 获取指定任务的审批决策（用于 Agent 等待 operator 决策）。
     */
    public ApprovalDecision getApprovalDecision(String taskId) throws IOException {
        Request request = new Request.Builder()
                .url(baseUrl + "/api/v1/agent/tasks/" + taskId + "/approval")
                .header("X-Agent-Token", agentToken)
                .get()
                .build();

        try (Response response = httpClient.newCall(request).execute()) {
            if (!response.isSuccessful()) {
                throw new IOException("approval status failed: " + response.code());
            }
            String body = response.body().string();
            ApiResponse<ApprovalStatusResponse> apiResponse = objectMapper.readValue(
                    body,
                    new TypeReference<ApiResponse<ApprovalStatusResponse>>() {
                    }
            );
            String decision = apiResponse.getPayload() != null ? apiResponse.getPayload().getDecision() : "pending";
            return switch (decision.toLowerCase()) {
                case "approve", "approved" -> ApprovalDecision.APPROVE;
                case "reject", "rejected" -> ApprovalDecision.REJECT;
                default -> ApprovalDecision.PENDING;
            };
        }
    }

    private Request post(String path, Object payload) throws IOException {
        String body = objectMapper.writeValueAsString(payload);
        return new Request.Builder()
                .url(baseUrl + path)
                .header("X-Agent-Token", agentToken)
                .post(RequestBody.create(body, JSON))
                .build();
    }

    private void executeNoPayload(Request request) throws IOException {
        try (Response response = httpClient.newCall(request).execute()) {
            if (!response.isSuccessful()) {
                String error = response.body() != null ? response.body().string() : "";
                throw new IOException("request failed: " + response.code() + " " + error);
            }
        }
    }
}
