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
import com.autocode.protocol.model.TaskEvent;
import com.autocode.protocol.model.TaskSummary;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicLong;

public class TaskExecutor {
    private static final Logger log = LoggerFactory.getLogger(TaskExecutor.class);

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
        maybePublishPostSuccessArtifacts(task, traceId, runId, cwd);

        long totalMs = (System.nanoTime() - taskStartNs) / 1_000_000;
        log.info("Task {} done total {}ms traceId={} runId={}", task.getTaskId(), totalMs, traceId, runId);
        send(task, traceId, runId, EventType.TASK_DONE, Map.of("result", "success"));
    }

    private void maybePublishPostSuccessArtifacts(TaskSummary task, String traceId, String runId, String cwd) {
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
                publishOnePostSuccessArtifact(task, traceId, runId, cwd, raw);
            } catch (Exception ex) {
                log.warn("post-success artifact upload skipped for {}: {}", raw, ex.getMessage());
            }
        }
    }

    private void publishOnePostSuccessArtifact(TaskSummary task, String traceId, String runId, String cwd, String raw)
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
        String kind = LocalArtifactMapper.inferKind(meta);
        if (kind == null || kind.isBlank()) {
            kind = LocalArtifactMapper.inferArtifactType(filename);
        }
        send(task, traceId, runId, EventType.ARTIFACT_READY, ArtifactReadyPayloads.fromMetadata(meta, kind));
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
        if (v == null || v.isBlank()) {
            return null;
        }
        return v.trim();
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
            event.setSessionId(readSessionIdCompat(task));
        }
        event.setSeq(Math.max(0, seq));
        // payload is set by caller (merged with traceId/runId in send()).
        return event;
    }

    /**
     * Prefer protocol-level sessionId; fall back to legacy sessionKey for backward compatibility.
     */
    private static String readSessionIdCompat(TaskSummary task) {
        if (task == null) {
            return null;
        }
        String sid = invokeStringGetter(task, "getSessionId");
        if (sid != null && !sid.isBlank()) {
            return sid;
        }
        String sk = invokeStringGetter(task, "getSessionKey");
        if (sk != null && !sk.isBlank()) {
            return sk;
        }
        return null;
    }

    /**
     * shared-protocol may evolve; keep agent compatible with older TaskSummary shapes that don't expose workspacePath.
     */
    private static String readWorkspacePathCompat(TaskSummary task) {
        if (task == null) {
            return null;
        }
        String value = invokeStringGetter(task, "getWorkspacePath");
        if (value == null || value.isBlank()) {
            return null;
        }
        return value;
    }

    private static String invokeStringGetter(TaskSummary task, String getterName) {
        try {
            Method m = task.getClass().getMethod(getterName);
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
