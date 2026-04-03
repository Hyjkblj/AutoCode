/**
 * HTTP client for the control plane agent endpoints (register/heartbeat/poll/publish events).
 */
package com.autocode.agent.client;

import com.autocode.agent.config.AgentConfig;
import com.autocode.protocol.model.ApprovalDecision;
import com.autocode.protocol.model.ArtifactMetadata;
import com.autocode.protocol.model.GatewayResponse;
import com.autocode.protocol.model.TaskEvent;
import com.autocode.protocol.model.TaskSummary;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import okhttp3.HttpUrl;
import okhttp3.MediaType;
import okhttp3.MultipartBody;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

import java.io.IOException;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.TimeUnit;
import java.security.GeneralSecurityException;

public class AgentApiClient {
    private static final MediaType JSON = MediaType.get("application/json; charset=utf-8");
    private static final String DEFAULT_AGENT_VERSION = "0.1.0";

    private final OkHttpClient httpClient;
    private final ObjectMapper objectMapper;
    private final String baseUrl;
    private final String agentToken;
    private final String agentProfile;
    private final String agentVersion;
    private final String userAgent;

    /**
     * Backward-compatible constructor for tests and simple embeds (default profile + HTTP timeouts).
     */
    public AgentApiClient(String baseUrl, String agentToken) {
        this(baseUrl, agentToken, "coder", AgentConfig.HttpTimeouts.DEFAULTS, AgentConfig.ClientTls.DISABLED,
                DEFAULT_AGENT_VERSION);
    }

    public AgentApiClient(String baseUrl, String agentToken, String agentProfile, AgentConfig.HttpTimeouts httpTimeouts) {
        this(baseUrl, agentToken, agentProfile, httpTimeouts, AgentConfig.ClientTls.DISABLED, DEFAULT_AGENT_VERSION);
    }

    public AgentApiClient(
            String baseUrl,
            String agentToken,
            String agentProfile,
            AgentConfig.HttpTimeouts httpTimeouts,
            AgentConfig.ClientTls clientTls) {
        this(baseUrl, agentToken, agentProfile, httpTimeouts, clientTls, DEFAULT_AGENT_VERSION);
    }

    public AgentApiClient(
            String baseUrl,
            String agentToken,
            String agentProfile,
            AgentConfig.HttpTimeouts httpTimeouts,
            AgentConfig.ClientTls clientTls,
            String agentVersion) {
        this.baseUrl = baseUrl.endsWith("/") ? baseUrl.substring(0, baseUrl.length() - 1) : baseUrl;
        this.agentToken = agentToken;
        String profile = agentProfile == null || agentProfile.isBlank() ? "coder" : agentProfile.trim().toLowerCase();
        this.agentProfile = profile;
        String v = agentVersion == null || agentVersion.isBlank() ? DEFAULT_AGENT_VERSION : agentVersion.trim();
        this.agentVersion = v;
        this.userAgent = "AutoCode-Java-Agent/" + v;
        AgentConfig.HttpTimeouts t = httpTimeouts != null ? httpTimeouts : AgentConfig.HttpTimeouts.DEFAULTS;
        AgentConfig.ClientTls tls = clientTls != null ? clientTls : AgentConfig.ClientTls.DISABLED;
        OkHttpClient.Builder httpBuilder = new OkHttpClient.Builder()
                .connectTimeout(t.getConnectSeconds(), TimeUnit.SECONDS)
                .readTimeout(t.getReadSeconds(), TimeUnit.SECONDS)
                .writeTimeout(t.getWriteSeconds(), TimeUnit.SECONDS)
                .callTimeout(t.getCallSeconds(), TimeUnit.SECONDS);
        try {
            AgentTlsSocketFactory.apply(httpBuilder, tls);
        } catch (IOException | GeneralSecurityException e) {
            throw new IllegalStateException("TLS setup failed for control plane client: " + e.getMessage(), e);
        }
        this.httpClient = httpBuilder.build();
        this.objectMapper = new ObjectMapper();
        this.objectMapper.registerModule(new JavaTimeModule());
    }

    /**
     * 注册节点到控制平面（用于可见性与在线状态管理）。
     */
    public void register(String nodeId) throws IOException {
        Map<String, Object> body = Map.of(
                "nodeId", nodeId,
                "version", agentVersion,
                "capabilities", "codex,events,approval,profile:" + agentProfile
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
        HttpUrl url = HttpUrl.parse(baseUrl + "/api/v1/agent/tasks/next")
                .newBuilder()
                .addQueryParameter("nodeId", nodeId)
                .addQueryParameter("profile", agentProfile)
                .build();

        Request request = authorizedBuilder()
                .url(url)
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
     * 上传任务产物（multipart，对齐控制面 {@code POST /api/v1/tasks/{taskId}/artifacts}），并解析返回的
     * {@link ArtifactMetadata}（可用于组装 {@code ARTIFACT_READY} 事件，见 {@link ArtifactReadyPayloads}）。
     *
     * @param filename multipart 文件名（{@code Content-Disposition}）
     * @param logicalName 可选的登记名称（表单字段 {@code name}）；为 null 时使用 {@code filename}
     */
    public ArtifactMetadata uploadArtifact(String taskId, String filename, String logicalName, String contentType,
                                           byte[] data) throws IOException {
        if (data == null) {
            throw new IllegalArgumentException("data is required");
        }
        String fn = (filename == null || filename.isBlank()) ? "artifact.bin" : filename;
        MediaType ct = MediaType.parse(
                contentType != null && !contentType.isBlank() ? contentType : "application/octet-stream");
        RequestBody fileBody = RequestBody.create(data, ct);
        MultipartBody.Builder builder = new MultipartBody.Builder()
                .setType(MultipartBody.FORM)
                .addFormDataPart("file", fn, fileBody);
        if (logicalName != null && !logicalName.isBlank()) {
            builder.addFormDataPart("name", logicalName);
        }
        Request request = authorizedBuilder()
                .url(baseUrl + "/api/v1/tasks/" + taskId + "/artifacts")
                .post(builder.build())
                .build();
        try (Response response = httpClient.newCall(request).execute()) {
            String body = response.body() != null ? response.body().string() : "";
            if (!response.isSuccessful()) {
                throw new IOException("artifact upload failed: " + response.code() + " " + body);
            }
            GatewayResponse gateway = objectMapper.readValue(body, GatewayResponse.class);
            if (!gateway.isOk() || gateway.getPayload() == null) {
                throw new IOException("artifact upload rejected: " + (gateway.getError() != null ? gateway.getError() : "no payload"));
            }
            return toArtifactMetadata(gateway.getPayload());
        }
    }

    /** 使用默认内容类型上传产物（{@code application/octet-stream}）。 */
    public ArtifactMetadata uploadArtifact(String taskId, String filename, byte[] data) throws IOException {
        return uploadArtifact(taskId, filename, null, null, data);
    }

    /**
     * 获取指定任务的审批决策（用于 Agent 等待 operator 决策）。
     */
    public ApprovalDecision getApprovalDecision(String taskId) throws IOException {
        Request request = authorizedBuilder()
                .url(baseUrl + "/api/v1/agent/tasks/" + taskId + "/approval")
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

    private Request.Builder authorizedBuilder() {
        return new Request.Builder()
                .header("X-Agent-Token", agentToken)
                .header("User-Agent", userAgent);
    }

    private Request post(String path, Object payload) throws IOException {
        String body = objectMapper.writeValueAsString(payload);
        return authorizedBuilder()
                .url(baseUrl + path)
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

    private ArtifactMetadata toArtifactMetadata(Object payload) {
        ArtifactMetadata metadata = objectMapper.convertValue(payload, ArtifactMetadata.class);
        if (!(payload instanceof Map<?, ?> map)) {
            return metadata;
        }
        if (isBlank(metadata.getHash())) {
            String hash = asTrimmedString(map.get("sha256"));
            if (hash != null) {
                metadata.setHash(hash);
            }
        }
        if (metadata.getSize() == null) {
            Long size = asLong(map.get("sizeBytes"));
            if (size != null) {
                metadata.setSize(size);
            }
        }
        if (isBlank(metadata.getMime())) {
            String contentType = asTrimmedString(map.get("contentType"));
            if (contentType != null) {
                metadata.setMime(contentType);
            }
        }
        if (isBlank(metadata.getName())) {
            String name = asTrimmedString(map.get("name"));
            if (name != null) {
                metadata.setName(name);
            }
        }
        return metadata;
    }

    private static Long asLong(Object value) {
        if (value == null) {
            return null;
        }
        if (value instanceof Number n) {
            return n.longValue();
        }
        if (value instanceof String s) {
            try {
                return Long.parseLong(s.trim());
            } catch (NumberFormatException ignored) {
                return null;
            }
        }
        return null;
    }

    private static String asTrimmedString(Object value) {
        if (!(value instanceof String s)) {
            return null;
        }
        String trimmed = s.trim();
        return trimmed.isEmpty() ? null : trimmed;
    }

    private static boolean isBlank(String value) {
        return value == null || value.trim().isEmpty();
    }
}
