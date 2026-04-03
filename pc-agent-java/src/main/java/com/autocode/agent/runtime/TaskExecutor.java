/**
 * Task execution orchestrator on the node: policy checks, optional approval wait, then tool execution.
 */
package com.autocode.agent.runtime;

import com.autocode.agent.artifact.LocalArtifactMapper;
import com.autocode.agent.client.AgentApiClient;
import com.autocode.agent.client.ArtifactReadyPayloads;
import com.autocode.agent.config.AgentConfig;
import com.autocode.agent.runtime.exec.CommandRunner;
import com.autocode.agent.runtime.git.GitDiffCollector;
import com.autocode.agent.runtime.tool.Tool;
import com.autocode.agent.runtime.tool.ToolCall;
import com.autocode.agent.runtime.tool.ToolContext;
import com.autocode.agent.runtime.tool.ToolExecutionResult;
import com.autocode.agent.runtime.tool.ToolRegistry;
import com.autocode.agent.runtime.tool.impl.CommandExecTool;
import com.autocode.agent.security.CommandSafetyPolicy;
import com.autocode.agent.security.WorkspacePrefixGuard;
import com.autocode.agent.security.PromptCommandExtractor;
import com.autocode.agent.security.policy.CompositeToolInvocationPolicy;
import com.autocode.agent.security.policy.PolicyDecision;
import com.autocode.agent.security.policy.WorkspaceAllowlistPolicy;
import com.autocode.protocol.model.ApprovalDecision;
import com.autocode.protocol.model.ArtifactMetadata;
import com.autocode.protocol.model.EventType;
import com.autocode.protocol.model.ServiceRuntimeDescriptor;
import com.autocode.protocol.model.TaskEvent;
import com.autocode.protocol.model.TaskSummary;
import com.autocode.protocol.validation.ServiceRuntimeDescriptorContractValidator;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicLong;

public class TaskExecutor {
    private static final Logger log = LoggerFactory.getLogger(TaskExecutor.class);
    private static final ObjectMapper JSON = new ObjectMapper();
    private static final String DEFAULT_RUNTIME_DESCRIPTOR_FILE = "service_runtime_descriptor.v1.json";

    private final AgentApiClient client;
    private final PromptCommandExtractor promptCommandExtractor;
    private volatile AgentConfig config;
    private final CommandRunner commandRunner;
    private final GitDiffCollector gitDiffCollector;
    private final ToolRegistry toolRegistry;
    private volatile CompositeToolInvocationPolicy invocationPolicy;
    private final AtomicLong seq = new AtomicLong(0);

    public TaskExecutor(AgentApiClient client, AgentConfig config) {
        this.client = client;
        this.config = config;
        this.promptCommandExtractor = new PromptCommandExtractor();
        this.commandRunner = new CommandRunner();
        this.gitDiffCollector = new GitDiffCollector(this.commandRunner);
        this.toolRegistry = new ToolRegistry();
        rebuildFromConfig(config);
    }

    public void updateConfig(AgentConfig config) {
        if (config == null) {
            return;
        }
        this.config = config;
        rebuildFromConfig(config);
    }

    private void rebuildFromConfig(AgentConfig config) {
        // MVP: registry is in-memory; re-register built-ins with latest policies.
        toolRegistry.clear()
                .register(new CommandExecTool(
                        new CommandSafetyPolicy(config.getAllowedCommandPrefixes(), config.isNetworkAllowed()),
                        this.commandRunner));
        this.invocationPolicy = CompositeToolInvocationPolicy.builder()
                .add(new WorkspaceAllowlistPolicy(config.getAllowedWorkspacePrefixes()))
                .build();
    }

    /**
     * 执行单个任务：先做命令提取/白名单校验，再按策略触发审批，最后执行命令并上报事件。
     */
    public void execute(TaskSummary task) throws IOException, InterruptedException {
        String traceId = "trc_" + task.getTaskId();
        String runId = "run_" + UUID.randomUUID().toString().replace("-", "");
        long taskStartNs = System.nanoTime();

        String command = promptCommandExtractor.extractCommand(task.getPrompt());
        String workspacePath = readWorkspacePathCompat(task);
        String cwd = (workspacePath == null || workspacePath.isBlank())
                ? System.getProperty("user.dir", "")
                : workspacePath;
        ToolCall call = new ToolCall(
                "command.exec",
                "run_command",
                Map.of(
                        "command", command,
                        "prompt", task.getPrompt()
                )
        );
        String approvalIdForExec = null;

        Tool tool = toolRegistry.getRequired(call.getTool());
        ToolContext preCtx = new ToolContext(task, cwd, null, config.getApprovalTimeoutSeconds());
        PolicyDecision policyDecision = invocationPolicy.evaluate(call, preCtx);
        if (!policyDecision.isAllowed()) {
            send(task, traceId, runId, EventType.TASK_FAILED, Map.of(
                    "reason", "policy_denied",
                    "policyReason", policyDecision.getReason(),
                    "tool", call.getTool(),
                    "cwd", cwd
            ));
            return;
        }
        if (!tool.policy().isAllowed(call)) {
            // 不在允许范围内：直接失败并上报原因（控制平面会落库/广播）
            send(task, traceId, runId, EventType.TASK_FAILED, Map.of(
                    "reason", "command_not_allowed",
                    "command", command
            ));
            return;
        }

        send(task, traceId, runId, EventType.ASSISTANT_OUTPUT, Map.of(
                "message", "Task accepted by node, preparing execution.",
                "command", command
        ));

        if (tool.policy().requiresApproval(call)) {
            String approvalId = "apr_" + UUID.randomUUID().toString().replace("-", "");
            approvalIdForExec = approvalId;
            // 触发审批：控制平面会把任务置为 WAITING_APPROVAL，并要求 operator 决策
            ToolContext approvalCtx = new ToolContext(task, cwd, approvalId, config.getApprovalTimeoutSeconds());
            send(task, traceId, runId, EventType.APPROVAL_REQUIRED, tool.buildApprovalPayload(call, approvalCtx));

            // 等待审批结果：通过 control plane 的 approval 状态接口轮询
            long approvalStartNs = System.nanoTime();
            ApprovalDecision decision = waitForApproval(task.getTaskId());
            long approvalWaitMs = (System.nanoTime() - approvalStartNs) / 1_000_000;
            log.info("Task {} approval wait {}ms traceId={} runId={}", task.getTaskId(), approvalWaitMs, traceId, runId);
            send(task, traceId, runId, EventType.APPROVAL_RESULT, Map.of(
                    "approvalId", approvalId,
                    "decision", decision.name().toLowerCase(),
                    "waitMs", approvalWaitMs
            ));
            if (decision == ApprovalDecision.REJECT) {
                send(task, traceId, runId, EventType.TASK_FAILED, Map.of("reason", "approval_rejected"));
                return;
            }
            if (decision == ApprovalDecision.PENDING) {
                send(task, traceId, runId, EventType.TASK_FAILED, Map.of("reason", "approval_timeout"));
                return;
            }
        }

        // 开始执行：以 TOOL_START/TOOL_END 形式上报，便于前端展示工具调用过程
        HashMap<String, Object> toolStart = new HashMap<>();
        toolStart.put("tool", call.getTool());
        toolStart.put("command", command);
        toolStart.put("cwd", cwd);
        toolStart.put("action", call.getAction());
        if (approvalIdForExec != null) {
            toolStart.put("approvalId", approvalIdForExec);
        }
        send(task, traceId, runId, EventType.TOOL_START, toolStart);

        ToolExecutionResult exec;
        long execStartNs = System.nanoTime();
        try {
            ToolContext execCtx = new ToolContext(task, cwd, approvalIdForExec, config.getApprovalTimeoutSeconds());
            exec = tool.execute(call, execCtx);
        } catch (InterruptedException ie) {
            throw ie;
        } catch (IOException ex) {
            send(task, traceId, runId, EventType.TOOL_END, Map.of(
                    "tool", call.getTool(),
                    "status", "error",
                    "error", ex.getMessage() == null ? "io_error" : ex.getMessage()
            ));
            send(task, traceId, runId, EventType.TASK_FAILED, Map.of("reason", "exec_io_error"));
            return;
        } catch (Exception ex) {
            send(task, traceId, runId, EventType.TOOL_END, Map.of(
                    "tool", call.getTool(),
                    "status", "error",
                    "error", ex.getMessage() == null ? "exec_error" : ex.getMessage()
            ));
            send(task, traceId, runId, EventType.TASK_FAILED, Map.of("reason", "exec_error"));
            return;
        }
        long execMs = (System.nanoTime() - execStartNs) / 1_000_000;
        log.info("Task {} tool {} exec {}ms traceId={} runId={}", task.getTaskId(), call.getTool(), execMs, traceId, runId);

        send(task, traceId, runId, EventType.TOOL_END, exec.getToolEndPayload());

        if (!exec.isSuccess()) {
            Object status = exec.getToolEndPayload().get("status");
            Object exitCode = exec.getToolEndPayload().get("exitCode");
            if ("timeout".equals(status)) {
                send(task, traceId, runId, EventType.TASK_FAILED, Map.of("reason", "exec_timeout"));
                return;
            }
            if (exitCode instanceof Number n && n.intValue() != 0) {
                send(task, traceId, runId, EventType.TASK_FAILED, Map.of(
                        "reason", "exec_nonzero_exit",
                        "exitCode", n.intValue()
                ));
                return;
            }
            send(task, traceId, runId, EventType.TASK_FAILED, Map.of("reason", "exec_failed"));
            return;
        }

        // 产出真实 patch 预览：若 workspacePath 指向 git 仓库且存在 diff，则上报 FILE_PATCH_PREVIEW
        try {
            Map<String, Object> patchPreview = gitDiffCollector.collectPatchPreview(cwd);
            if (patchPreview != null) {
                send(task, traceId, runId, EventType.FILE_PATCH_PREVIEW, patchPreview);
            }
        } catch (Exception ignored) {
            // 预览属于附加信息，失败不影响主任务完成
        }

        // M1/M2：可选将本地产物上传并上报 ARTIFACT_READY（路径须在工作区前缀白名单内）
        maybePublishPostSuccessArtifacts(task, traceId, runId, cwd, command);
        maybePublishRuntimeDescriptor(task, traceId, runId, cwd, command);

        long totalMs = (System.nanoTime() - taskStartNs) / 1_000_000;
        log.info("Task {} done total {}ms traceId={} runId={}", task.getTaskId(), totalMs, traceId, runId);
        send(task, traceId, runId, EventType.TASK_DONE, Map.of("result", "success"));
    }

    private void maybePublishPostSuccessArtifacts(
            TaskSummary task,
            String traceId,
            String runId,
            String cwd,
            String command) {
        String multi = System.getenv("MVP_POST_SUCCESS_ARTIFACT_PATHS");
        String single = System.getenv("MVP_POST_SUCCESS_ARTIFACT_PATH");
        List<String> rawPaths = new ArrayList<>();
        if (multi != null && !multi.isBlank()) {
            for (String p : multi.split(",")) {
                String t = p.trim();
                if (!t.isEmpty()) {
                    rawPaths.add(t);
                }
            }
        } else if (single != null && !single.isBlank()) {
            rawPaths.add(single.trim());
        }
        if (rawPaths.isEmpty()) {
            return;
        }
        for (String raw : rawPaths) {
            try {
                publishOnePostSuccessArtifact(task, traceId, runId, cwd, command, raw);
            } catch (Exception ex) {
                log.warn("post-success artifact upload skipped for {}: {}", raw, ex.getMessage());
            }
        }
    }

    private void publishOnePostSuccessArtifact(
            TaskSummary task,
            String traceId,
            String runId,
            String cwd,
            String command,
            String raw)
            throws IOException {
        Path cwdPath = Path.of(cwd).toAbsolutePath().normalize();
        Path artifactPath;
        try {
            artifactPath = resolveArtifactPath(raw.trim(), cwdPath);
        } catch (SecurityException e) {
            log.warn("artifact path rejected: {}", e.getMessage());
            return;
        }
        if (!Files.isRegularFile(artifactPath)) {
            log.warn("post-success artifact path is not a regular file: {}", artifactPath);
            return;
        }
        String normalizedArtifact = WorkspacePrefixGuard.normalizePath(artifactPath.toString());
        if (!WorkspacePrefixGuard.isPathUnderAllowedPrefixes(
                normalizedArtifact, config.getAllowedWorkspacePrefixes())) {
            log.warn("artifact path outside MVP_ALLOWED_WORKSPACE_PREFIXES: {}", artifactPath);
            return;
        }
        long maxBytes = parseArtifactUploadMaxBytes();
        long sz = Files.size(artifactPath);
        if (sz > maxBytes) {
            log.warn("artifact too large ({} bytes > {} max): {}", sz, maxBytes, artifactPath);
            return;
        }
        byte[] data = Files.readAllBytes(artifactPath);
        String filename = artifactPath.getFileName().toString();
        String contentType = LocalArtifactMapper.guessMimeType(filename);
        String logicalName = readOptionalEnv("MVP_ARTIFACT_LOGICAL_NAME");
        ArtifactMetadata meta = client.uploadArtifact(
                task.getTaskId(), filename, logicalName, contentType, data);
        LocalArtifactMapper.applyServerMetadataDefaults(meta, filename);
        applyRuntimeHints(meta, command, System.getenv());
        String kind = LocalArtifactMapper.inferKind(meta);
        if (kind == null || kind.isBlank()) {
            kind = LocalArtifactMapper.inferArtifactType(filename);
        }
        send(task, traceId, runId, EventType.ARTIFACT_READY, ArtifactReadyPayloads.fromMetadata(meta, kind));
    }

    private void maybePublishRuntimeDescriptor(
            TaskSummary task,
            String traceId,
            String runId,
            String cwd,
            String command) {
        Map<String, String> env = System.getenv();
        ServiceRuntimeDescriptor descriptor = buildRuntimeDescriptor(task, command, cwd, env);
        if (descriptor == null) {
            return;
        }
        try {
            ServiceRuntimeDescriptorContractValidator.validate(descriptor);
        } catch (Exception ex) {
            log.warn("runtime descriptor contract violation, skip report: {}", ex.getMessage());
            return;
        }
        String fileName = readOptionalEnv(env, "MVP_RUNTIME_DESCRIPTOR_FILE");
        if (fileName == null) {
            fileName = DEFAULT_RUNTIME_DESCRIPTOR_FILE;
        }
        String logicalName = readOptionalEnv(env, "MVP_RUNTIME_DESCRIPTOR_LOGICAL_NAME");
        String kind = firstNonBlank(readOptionalEnv(env, "MVP_RUNTIME_ARTIFACT_KIND"), "runtime");
        try {
            byte[] body = JSON.writeValueAsBytes(descriptor);
            ArtifactMetadata metadata = client.uploadArtifact(
                    task.getTaskId(),
                    fileName,
                    logicalName,
                    "application/json",
                    body);
            LocalArtifactMapper.applyServerMetadataDefaults(metadata, fileName);
            String type = metadata.getType() == null ? "" : metadata.getType().trim();
            if (type.isEmpty() || "binary".equalsIgnoreCase(type)) {
                metadata.setType("runtime");
            }
            if (metadata.getMime() == null || metadata.getMime().isBlank()) {
                metadata.setMime("application/json");
            }
            if (metadata.getName() == null || metadata.getName().isBlank()) {
                metadata.setName(fileName);
            }
            applyRuntimeHints(metadata, command, env);
            send(task, traceId, runId, EventType.ARTIFACT_READY, ArtifactReadyPayloads.fromMetadata(metadata, kind));
        } catch (Exception ex) {
            log.warn("runtime descriptor upload skipped: {}", ex.getMessage());
        }
    }

    static ServiceRuntimeDescriptor buildRuntimeDescriptor(
            TaskSummary task,
            String executedCommand,
            String cwd,
            Map<String, String> env) {
        if (!isRuntimeReportingEnabled(env)) {
            return null;
        }
        String serviceId = firstNonBlank(
                readOptionalEnv(env, "MVP_RUNTIME_SERVICE_ID"),
                task == null ? null : trimToNull(task.getTaskId()));
        if (serviceId == null) {
            return null;
        }

        ServiceRuntimeDescriptor descriptor = new ServiceRuntimeDescriptor();
        descriptor.setSchemaVersion(1);
        descriptor.setServiceId(serviceId);
        descriptor.setDisplayName(readOptionalEnv(env, "MVP_RUNTIME_DISPLAY_NAME"));

        Integer port = parsePositivePort(readOptionalEnv(env, "MVP_RUNTIME_PORT"));
        if (port != null) {
            ServiceRuntimeDescriptor.PortBinding binding = new ServiceRuntimeDescriptor.PortBinding();
            binding.setName(firstNonBlank(readOptionalEnv(env, "MVP_RUNTIME_PORT_NAME"), "http"));
            binding.setProtocol(firstNonBlank(readOptionalEnv(env, "MVP_RUNTIME_PORT_PROTOCOL"), "http"));
            binding.setPort(port);
            descriptor.setPorts(List.of(binding));
        }

        String healthPath = normalizeHealthPath(readOptionalEnv(env, "MVP_RUNTIME_HEALTH_PATH"));
        if (healthPath != null) {
            ServiceRuntimeDescriptor.HealthCheckSpec healthCheck = new ServiceRuntimeDescriptor.HealthCheckSpec();
            healthCheck.setPath(healthPath);
            healthCheck.setMethod(firstNonBlank(
                    readOptionalEnv(env, "MVP_RUNTIME_HEALTH_METHOD"),
                    "GET").toUpperCase(Locale.ROOT));
            String healthPortName = firstNonBlank(
                    readOptionalEnv(env, "MVP_RUNTIME_HEALTH_PORT_NAME"),
                    descriptor.getPorts() == null || descriptor.getPorts().isEmpty()
                            ? null
                            : descriptor.getPorts().get(0).getName());
            if (healthPortName != null) {
                healthCheck.setPortName(healthPortName);
            }
            descriptor.setHealthCheck(healthCheck);
        }

        String startupCommand = firstNonBlank(
                readOptionalEnv(env, "MVP_RUNTIME_START_COMMAND"),
                trimToNull(executedCommand));
        if (startupCommand != null) {
            ServiceRuntimeDescriptor.StartupDescriptor startup = new ServiceRuntimeDescriptor.StartupDescriptor();
            startup.setCommand(startupCommand);
            startup.setWorkingDir(firstNonBlank(readOptionalEnv(env, "MVP_RUNTIME_WORKING_DIR"), trimToNull(cwd)));
            List<String> args = parseCsv(readOptionalEnv(env, "MVP_RUNTIME_START_ARGS"));
            if (!args.isEmpty()) {
                startup.setArgs(args);
            }
            descriptor.setStartup(startup);
        }
        return descriptor;
    }

    static ArtifactMetadata.RunDescriptor buildRunDescriptor(
            ArtifactMetadata.RunDescriptor existing,
            String executedCommand,
            Map<String, String> env) {
        String command = firstNonBlank(
                readOptionalEnv(env, "MVP_RUNTIME_RUN_COMMAND"),
                existing == null ? null : trimToNull(existing.getCommand()),
                trimToNull(executedCommand));

        LinkedHashSet<String> hints = new LinkedHashSet<>();
        if (existing != null && existing.getHints() != null) {
            for (String hint : existing.getHints()) {
                String normalized = trimToNull(hint);
                if (normalized != null) {
                    hints.add(normalized);
                }
            }
        }

        String explicitHealthUrl = readOptionalEnv(env, "MVP_RUNTIME_HEALTH_URL");
        if (explicitHealthUrl != null) {
            hints.add(explicitHealthUrl);
        } else {
            String healthPath = normalizeHealthPath(readOptionalEnv(env, "MVP_RUNTIME_HEALTH_PATH"));
            if (healthPath != null) {
                String healthBase = buildHealthBaseUrl(env);
                hints.add(healthBase == null ? healthPath : healthBase + healthPath);
            }
        }

        for (String hint : parseCsv(readOptionalEnv(env, "MVP_RUNTIME_RUN_HINTS"))) {
            hints.add(hint);
        }

        if (command == null && hints.isEmpty()) {
            return null;
        }
        ArtifactMetadata.RunDescriptor run = existing != null ? existing : new ArtifactMetadata.RunDescriptor();
        run.setCommand(command);
        run.setHints(hints.isEmpty() ? null : new ArrayList<>(hints));
        return run;
    }

    private static void applyRuntimeHints(ArtifactMetadata metadata, String command, Map<String, String> env) {
        if (metadata == null) {
            return;
        }
        ArtifactMetadata.RunDescriptor run = buildRunDescriptor(metadata.getRun(), command, env);
        if (run != null) {
            metadata.setRun(run);
        }
    }

    private static boolean isRuntimeReportingEnabled(Map<String, String> env) {
        String flag = readOptionalEnv(env, "MVP_RUNTIME_REPORT_ENABLED");
        if (flag != null) {
            return isTruthy(flag);
        }
        return hasRuntimeSignals(env);
    }

    private static boolean hasRuntimeSignals(Map<String, String> env) {
        return readOptionalEnv(env, "MVP_RUNTIME_SERVICE_ID") != null
                || readOptionalEnv(env, "MVP_RUNTIME_DISPLAY_NAME") != null
                || readOptionalEnv(env, "MVP_RUNTIME_PORT") != null
                || readOptionalEnv(env, "MVP_RUNTIME_HEALTH_PATH") != null
                || readOptionalEnv(env, "MVP_RUNTIME_HEALTH_URL") != null
                || readOptionalEnv(env, "MVP_RUNTIME_START_COMMAND") != null
                || readOptionalEnv(env, "MVP_RUNTIME_RUN_COMMAND") != null
                || readOptionalEnv(env, "MVP_RUNTIME_RUN_HINTS") != null;
    }

    private static String buildHealthBaseUrl(Map<String, String> env) {
        Integer port = parsePositivePort(readOptionalEnv(env, "MVP_RUNTIME_PORT"));
        if (port == null) {
            return null;
        }
        String scheme = firstNonBlank(
                readOptionalEnv(env, "MVP_RUNTIME_HEALTH_SCHEME"),
                readOptionalEnv(env, "MVP_RUNTIME_PORT_PROTOCOL"),
                "http");
        String host = firstNonBlank(readOptionalEnv(env, "MVP_RUNTIME_HEALTH_HOST"), "127.0.0.1");
        return scheme + "://" + host + ":" + port;
    }

    private static Integer parsePositivePort(String value) {
        if (value == null) {
            return null;
        }
        try {
            int port = Integer.parseInt(value);
            if (port < 1 || port > 65535) {
                return null;
            }
            return port;
        } catch (NumberFormatException ex) {
            return null;
        }
    }

    private static String normalizeHealthPath(String path) {
        String value = trimToNull(path);
        if (value == null) {
            return null;
        }
        return value.startsWith("/") ? value : "/" + value;
    }

    private static boolean isTruthy(String value) {
        String v = value.trim().toLowerCase(Locale.ROOT);
        return "1".equals(v) || "true".equals(v) || "yes".equals(v) || "on".equals(v);
    }

    private static List<String> parseCsv(String raw) {
        if (raw == null || raw.isBlank()) {
            return List.of();
        }
        ArrayList<String> values = new ArrayList<>();
        for (String p : raw.split(",")) {
            String normalized = trimToNull(p);
            if (normalized != null) {
                values.add(normalized);
            }
        }
        return values;
    }

    private static Path resolveArtifactPath(String raw, Path cwdPath) {
        Path p = Path.of(raw);
        if (p.isAbsolute()) {
            return p.normalize();
        }
        Path resolved = cwdPath.resolve(p).normalize();
        if (!resolved.startsWith(cwdPath)) {
            throw new SecurityException("path escapes workspace cwd");
        }
        return resolved;
    }

    private static long parseArtifactUploadMaxBytes() {
        String v = System.getenv("MVP_ARTIFACT_UPLOAD_MAX_BYTES");
        if (v == null || v.isBlank()) {
            return 256L * 1024 * 1024;
        }
        try {
            long n = Long.parseLong(v.trim());
            return n > 0 ? n : 256L * 1024 * 1024;
        } catch (NumberFormatException e) {
            return 256L * 1024 * 1024;
        }
    }

    private static String readOptionalEnv(String key) {
        String v = System.getenv(key);
        return trimToNull(v);
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

    private ApprovalDecision waitForApproval(String taskId) throws IOException, InterruptedException {
        int retries = Math.max(1, (int) (config.getApprovalTimeoutSeconds() / 2));
        while (retries-- > 0) {
            ApprovalDecision decision = client.getApprovalDecision(taskId);
            if (decision == ApprovalDecision.APPROVE || decision == ApprovalDecision.REJECT) {
                return decision;
            }
            Thread.sleep(2000);
        }
        return ApprovalDecision.PENDING;
    }

    private void send(TaskSummary task, String traceId, String runId, EventType type, Map<String, Object> payload) throws IOException {
        TaskEvent event = buildEvent(task, traceId, runId, type, payload, seq.getAndIncrement());
        event.setPayload(mergeOutboundPayload(type, traceId, runId, payload));
        client.publishEvent(task.getTaskId(), event);
    }

    /**
     * {@code ARTIFACT_READY} v1 JSON Schema allows only {@code artifact} and {@code kind} in payload — do not inject
     * {@code traceId}/{@code runId} there (M1 contract alignment).
     */
    static Map<String, Object> mergeOutboundPayload(EventType type, String traceId, String runId, Map<String, Object> payload) {
        HashMap<String, Object> merged = new HashMap<>();
        if (mergesCorrelationIntoPayload(type)) {
            merged.put("traceId", traceId);
            merged.put("runId", runId);
        }
        merged.putAll(payload);
        return merged;
    }

    static boolean mergesCorrelationIntoPayload(EventType type) {
        return type != EventType.ARTIFACT_READY;
    }

    static TaskEvent buildEvent(
            TaskSummary task,
            String traceId,
            String runId,
            EventType type,
            Map<String, Object> payload,
            long seq) {
        TaskEvent event = new TaskEvent();
        // Control plane validates eventId before ingest and uses it for idempotent deduplication.
        event.setEventId("evt_" + UUID.randomUUID().toString().replace("-", ""));
        event.setEventVersion(1);
        event.setType(type);
        event.setTimestamp(Instant.now());
        if (task != null) {
            event.setTaskId(task.getTaskId());
            event.setAssistant(task.getAssistant());
            String sessionId = firstNonBlank(readSessionIdCompat(task), task.getSessionKey());
            if (sessionId != null) {
                event.setSessionId(sessionId);
            }
        }
        event.setSeq(Math.max(0, seq));
        // payload is set by caller (merged with traceId/runId in send()).
        return event;
    }

    /**
     * shared-protocol may evolve; keep agent compatible with older TaskSummary shapes that don't expose workspacePath.
     */
    private static String readWorkspacePathCompat(TaskSummary task) {
        if (task == null) {
            return null;
        }
        try {
            Method m = task.getClass().getMethod("getWorkspacePath");
            Object v = m.invoke(task);
            if (v == null) {
                return null;
            }
            String s = String.valueOf(v).trim();
            return s.isEmpty() ? null : s;
        } catch (Exception ignored) {
            return null;
        }
    }

    private static String readSessionIdCompat(TaskSummary task) {
        if (task == null) {
            return null;
        }
        try {
            Method m = task.getClass().getMethod("getSessionId");
            Object v = m.invoke(task);
            if (v == null) {
                return null;
            }
            String s = String.valueOf(v).trim();
            return s.isEmpty() ? null : s;
        } catch (Exception ignored) {
            return null;
        }
    }
}
