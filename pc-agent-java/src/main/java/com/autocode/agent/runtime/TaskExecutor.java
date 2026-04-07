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
import com.autocode.agent.runtime.intent.IntentRouter;
import com.autocode.agent.runtime.intent.RoutedIntent;
import com.autocode.agent.runtime.intent.RuleBasedIntentRouter;
import com.autocode.agent.runtime.skill.Skill;
import com.autocode.agent.runtime.skill.SkillRegistry;
import com.autocode.agent.runtime.skill.impl.CodeExecSkill;
import com.autocode.agent.runtime.skill.impl.DeployExecuteSkill;
import com.autocode.agent.runtime.tool.Tool;
import com.autocode.agent.runtime.tool.ToolCall;
import com.autocode.agent.runtime.tool.ToolContext;
import com.autocode.agent.runtime.tool.ToolExecutionResult;
import com.autocode.agent.runtime.tool.ToolRegistry;
import com.autocode.agent.runtime.tool.impl.CommandExecTool;
import com.autocode.agent.security.CommandSafetyPolicy;
import com.autocode.agent.security.WorkspacePrefixGuard;
import com.autocode.agent.security.policy.CompositeToolInvocationPolicy;
import com.autocode.agent.security.policy.ElevationDetectionPolicy;
import com.autocode.agent.security.policy.EnvVarAccessPolicy;
import com.autocode.agent.security.policy.FileReadWritePolicy;
import com.autocode.agent.security.policy.NetworkAccessPolicy;
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
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.time.Instant;
import java.time.Duration;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HexFormat;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.TreeMap;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicLong;

public class TaskExecutor {
    private static final Logger log = LoggerFactory.getLogger(TaskExecutor.class);
    private static final ObjectMapper JSON = new ObjectMapper();
    private static final String DEFAULT_RUNTIME_DESCRIPTOR_FILE = "service_runtime_descriptor.v1.json";
    private static final String DEFAULT_DEPLOY_ACTION = "app.publish";
    private static final String DEFAULT_DEPLOY_TOOL = "deploy.execute";
    private static final String DEFAULT_DEPLOY_ARTIFACT_TYPE = "zip";

    private final AgentApiClient client;
    private volatile AgentConfig config;
    private volatile IntentRouter intentRouter;
    private final CommandRunner commandRunner;
    private final GitDiffCollector gitDiffCollector;
    private final ToolRegistry toolRegistry;
    private final SkillRegistry skillRegistry;
    private volatile CompositeToolInvocationPolicy invocationPolicy;
    private final AtomicLong seq = new AtomicLong(0);

    public TaskExecutor(AgentApiClient client, AgentConfig config) {
        this.client = client;
        this.config = config;
        this.commandRunner = new CommandRunner();
        this.gitDiffCollector = new GitDiffCollector(this.commandRunner);
        this.toolRegistry = new ToolRegistry();
        this.skillRegistry = new SkillRegistry();
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
        skillRegistry.clear()
                .register(new CodeExecSkill(),
                        "command.exec",
                        "skill.code.author")
                .register(new DeployExecuteSkill(),
                        "deploy.execute",
                        "skill.deploy.pipeline")
                .setDefaultSkill(CodeExecSkill.NAME);
        this.intentRouter = new RuleBasedIntentRouter(config.getIntentRules(), config.getAgentProfile());
        this.invocationPolicy = CompositeToolInvocationPolicy.builder()
                .add(new ElevationDetectionPolicy())
                .add(new EnvVarAccessPolicy())
                .add(new NetworkAccessPolicy(config.isNetworkAllowed()))
                .add(new FileReadWritePolicy(config.getAllowedWorkspacePrefixes()))
                .add(new WorkspaceAllowlistPolicy(config.getAllowedWorkspacePrefixes()))
                .build();
    }

    /**
     * 鎵ц鍗曚釜浠诲姟锛氬厛鍋氬懡浠ゆ彁鍙?鐧藉悕鍗曟牎楠岋紝鍐嶆寜绛栫暐瑙﹀彂瀹℃壒锛屾渶鍚庢墽琛屽懡浠ゅ苟涓婃姤浜嬩欢銆?
     */
    public void execute(TaskSummary task) throws IOException, InterruptedException {
        RoutedIntent intent = intentRouter.route(task);
        Skill skill = skillRegistry.resolve(intent.skill());
        skill.execute(new RoutedSkillContext(task, intent));
    }

    private void executeRoutedIntent(TaskSummary task, RoutedIntent intent, boolean forceDeploySkill)
            throws IOException, InterruptedException {
        String traceId = "trc_" + task.getTaskId();
        String runId = "run_" + UUID.randomUUID().toString().replace("-", "");
        long taskStartNs = System.nanoTime();

        RoutedIntent routedIntent = intent;
        String command = routedIntent.command();
        String workspacePath = readWorkspacePathCompat(task);
        String cwd = (workspacePath == null || workspacePath.isBlank())
                ? System.getProperty("user.dir", "")
                : workspacePath;
        ToolCall call = new ToolCall(routedIntent.tool(), routedIntent.action(), routedIntent.toToolArgs(task.getPrompt()));
        String approvalIdForExec = null;
        String requestedToolVersion = null;
        Object requestedVersionArg = call.getArgs().get("toolVersion");
        if (requestedVersionArg instanceof String s && !s.isBlank()) {
            requestedToolVersion = s.trim();
        }

        Tool tool;
        try {
            tool = toolRegistry.getRequired(call.getTool(), requestedToolVersion);
        } catch (IllegalArgumentException unknownTool) {
            log.warn("Task {} routed to unknown tool {}@{}, fallback to command.exec",
                    task.getTaskId(),
                    call.getTool(),
                    requestedToolVersion);
            routedIntent = RoutedIntent.fallback(command);
            command = routedIntent.command();
            call = new ToolCall(routedIntent.tool(), routedIntent.action(), routedIntent.toToolArgs(task.getPrompt()));
            tool = toolRegistry.getRequired(call.getTool(), null);
        }
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
            send(task, traceId, runId, EventType.TASK_FAILED, Map.of(
                    "reason", "command_not_allowed",
                    "command", command
            ));
            return;
        }

        HashMap<String, Object> assistantOutput = new HashMap<>();
        assistantOutput.put("message", "Task accepted by node, preparing execution.");
        assistantOutput.put("command", command);
        assistantOutput.put("intentSkill", routedIntent.skill());
        assistantOutput.put("intentRoute", routedIntent.routeSource());
        send(task, traceId, runId, EventType.ASSISTANT_OUTPUT, assistantOutput);

        if (tool.policy().requiresApproval(call)) {
            String approvalId = "apr_" + UUID.randomUUID().toString().replace("-", "");
            approvalIdForExec = approvalId;
            ToolContext approvalCtx = new ToolContext(task, cwd, approvalId, config.getApprovalTimeoutSeconds());
            send(task, traceId, runId, EventType.APPROVAL_REQUIRED, tool.buildApprovalPayload(call, approvalCtx));

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

        HashMap<String, Object> toolStart = new HashMap<>();
        toolStart.put("tool", call.getTool());
        String resolvedToolVersion = trimToNull(tool.version());
        if (resolvedToolVersion != null) {
            toolStart.put("toolVersion", resolvedToolVersion);
        }
        toolStart.put("command", command);
        toolStart.put("cwd", cwd);
        toolStart.put("action", call.getAction());
        toolStart.put("intentSkill", routedIntent.skill());
        toolStart.put("intentRoute", routedIntent.routeSource());
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

        try {
            Map<String, Object> patchPreview = gitDiffCollector.collectPatchPreview(cwd);
            if (patchPreview != null) {
                send(task, traceId, runId, EventType.FILE_PATCH_PREVIEW, patchPreview);
            }
        } catch (Exception ignored) {
            // Patch preview is optional and should not fail the task.
        }

        List<ArtifactMetadata> postSuccessArtifacts = maybePublishPostSuccessArtifacts(task, traceId, runId, cwd, command);
        maybePublishRuntimeDescriptor(task, traceId, runId, cwd, command);
        if (maybeReportDeployExecution(task, traceId, runId, cwd, command, postSuccessArtifacts, forceDeploySkill)) {
            return;
        }

        long totalMs = (System.nanoTime() - taskStartNs) / 1_000_000;
        log.info("Task {} done total {}ms traceId={} runId={}", task.getTaskId(), totalMs, traceId, runId);
        send(task, traceId, runId, EventType.TASK_DONE, Map.of("result", "success"));
    }

    private final class RoutedSkillContext implements Skill.Context {
        private final TaskSummary task;
        private final RoutedIntent intent;

        private RoutedSkillContext(TaskSummary task, RoutedIntent intent) {
            this.task = task;
            this.intent = intent;
        }

        @Override
        public TaskSummary task() {
            return task;
        }

        @Override
        public RoutedIntent intent() {
            return intent;
        }

        @Override
        public void runCodeExecution() throws IOException, InterruptedException {
            executeRoutedIntent(task, intent, false);
        }

        @Override
        public void runDeployExecution() throws IOException, InterruptedException {
            executeRoutedIntent(task, intent, true);
        }
    }

    private List<ArtifactMetadata> maybePublishPostSuccessArtifacts(
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
            return List.of();
        }
        ArrayList<ArtifactMetadata> uploaded = new ArrayList<>();
        for (String raw : rawPaths) {
            try {
                ArtifactMetadata metadata = publishOnePostSuccessArtifact(task, traceId, runId, cwd, command, raw);
                if (metadata != null) {
                    uploaded.add(metadata);
                }
            } catch (Exception ex) {
                log.warn("post-success artifact upload skipped for {}: {}", raw, ex.getMessage());
            }
        }
        return uploaded;
    }

    private ArtifactMetadata publishOnePostSuccessArtifact(
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
            return null;
        }
        if (!Files.isRegularFile(artifactPath)) {
            log.warn("post-success artifact path is not a regular file: {}", artifactPath);
            return null;
        }
        String normalizedArtifact = WorkspacePrefixGuard.normalizePath(artifactPath.toString());
        if (!WorkspacePrefixGuard.isPathUnderAllowedPrefixes(
                normalizedArtifact, config.getAllowedWorkspacePrefixes())) {
            log.warn("artifact path outside MVP_ALLOWED_WORKSPACE_PREFIXES: {}", artifactPath);
            return null;
        }
        long maxBytes = parseArtifactUploadMaxBytes();
        long sz = Files.size(artifactPath);
        if (sz > maxBytes) {
            log.warn("artifact too large ({} bytes > {} max): {}", sz, maxBytes, artifactPath);
            return null;
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
        return meta;
    }

    /**
     * Deploy flow for M4: optional approval gate -> DEPLOY_PLAN -> local execution -> DEPLOY_RESULT.
     *
     * @return true when the task flow should stop without sending TASK_DONE (for example: approval rejected/timeout).
     */
    private boolean maybeReportDeployExecution(
            TaskSummary task,
            String traceId,
            String runId,
            String cwd,
            String command,
            List<ArtifactMetadata> publishedArtifacts,
            boolean forceDeploySkill) throws IOException, InterruptedException {
        Map<String, String> env = System.getenv();
        if (!forceDeploySkill && !isDeployEnabled(env)) {
            return false;
        }

        String requestId = firstNonBlank(
                readOptionalEnv(env, "MVP_DEPLOY_REQUEST_ID"),
                "dep_req_" + UUID.randomUUID().toString().replace("-", ""));
        String environment = readOptionalEnv(env, "MVP_DEPLOY_ENVIRONMENT");
        if (environment == null) {
            log.warn("deploy reporting enabled but MVP_DEPLOY_ENVIRONMENT is missing");
            return false;
        }

        ArtifactMetadata deployArtifact = resolveDeployArtifact(publishedArtifacts, env);
        if (deployArtifact == null) {
            log.warn("deploy reporting enabled but no deploy artifact is available");
            return false;
        }

        Map<String, Object> deployContext = buildDeployContext(task, cwd, requestId, deployArtifact, env);
        String deployCommand = firstNonBlank(
                readOptionalEnv(env, "MVP_DEPLOY_COMMAND"),
                readOptionalEnv(env, "MVP_DEPLOY_EXEC_COMMAND"),
                command);
        boolean gateRequired = isTruthyOrDefault(readOptionalEnv(env, "MVP_DEPLOY_REQUIRE_APPROVAL"), true);
        if (gateRequired) {
            String approvalId = "apr_" + UUID.randomUUID().toString().replace("-", "");
            send(task, traceId, runId, EventType.APPROVAL_REQUIRED, buildDeployApprovalPayload(
                    approvalId,
                    deployCommand,
                    cwd,
                    deployContext,
                    config.getApprovalTimeoutSeconds(),
                    env));

            long approvalStartNs = System.nanoTime();
            ApprovalDecision decision = waitForApproval(task.getTaskId());
            long approvalWaitMs = (System.nanoTime() - approvalStartNs) / 1_000_000;
            send(task, traceId, runId, EventType.APPROVAL_RESULT, Map.of(
                    "approvalId", approvalId,
                    "decision", decision.name().toLowerCase(),
                    "waitMs", approvalWaitMs
            ));

            if (decision == ApprovalDecision.REJECT || decision == ApprovalDecision.PENDING) {
                String rejectedStatus = decision == ApprovalDecision.REJECT ? "rejected" : "canceled";
                String reason = decision == ApprovalDecision.REJECT ? "deploy approval rejected" : "deploy approval timeout";
                send(task, traceId, runId, EventType.DEPLOY_RESULT, buildDeployResultPayload(
                        requestId,
                        environment,
                        rejectedStatus,
                        reason,
                        env,
                        null,
                        Instant.now(),
                        Instant.now()
                ));
                return true;
            }
        }

        send(task, traceId, runId, EventType.DEPLOY_PLAN, buildDeployPlanPayload(
                requestId,
                environment,
                deployArtifact,
                deployContext,
                env
        ));

        Instant startedAt = Instant.now();
        String status = "success";
        String message = readOptionalEnv(env, "MVP_DEPLOY_SUCCESS_MESSAGE");
        ArtifactMetadata resultArtifact = resolveDeployResultArtifact(env);
        if (deployCommand != null) {
            Duration timeout = Duration.ofSeconds(parseLongOrDefault(readOptionalEnv(env, "MVP_DEPLOY_TIMEOUT_SECONDS"), 180L));
            var deployExec = commandRunner.run(deployCommand, timeout, cwd);
            if (deployExec.isTimedOut()) {
                status = "failed";
                message = firstNonBlank(message, "deploy command timed out");
            } else if (deployExec.getExitCode() != 0) {
                status = "failed";
                message = firstNonBlank(
                        message,
                        "deploy command exitCode=" + deployExec.getExitCode());
            } else {
                message = firstNonBlank(message, "deployment completed");
            }
        } else {
            message = firstNonBlank(message, "deployment reported without local execution command");
        }
        Instant finishedAt = Instant.now();
        send(task, traceId, runId, EventType.DEPLOY_RESULT, buildDeployResultPayload(
                requestId,
                environment,
                status,
                message,
                env,
                resultArtifact,
                startedAt,
                finishedAt
        ));

        if ("failed".equalsIgnoreCase(status)
                && isTruthyOrDefault(readOptionalEnv(env, "MVP_DEPLOY_FAIL_TASK_ON_FAILED_RESULT"), true)) {
            return true;
        }
        return false;
    }

    static boolean isDeployEnabled(Map<String, String> env) {
        String flag = readOptionalEnv(env, "MVP_DEPLOY_ENABLED");
        if (flag != null) {
            return isTruthy(flag);
        }
        return readOptionalEnv(env, "MVP_DEPLOY_ENVIRONMENT") != null;
    }

    private static ArtifactMetadata resolveDeployArtifact(List<ArtifactMetadata> publishedArtifacts, Map<String, String> env) {
        String artifactId = readOptionalEnv(env, "MVP_DEPLOY_ARTIFACT_ID");
        if (artifactId != null) {
            ArtifactMetadata metadata = new ArtifactMetadata();
            metadata.setArtifactId(artifactId);
            metadata.setType(firstNonBlank(
                    readOptionalEnv(env, "MVP_DEPLOY_ARTIFACT_TYPE"),
                    DEFAULT_DEPLOY_ARTIFACT_TYPE));
            metadata.setName(readOptionalEnv(env, "MVP_DEPLOY_ARTIFACT_NAME"));
            metadata.setMime(readOptionalEnv(env, "MVP_DEPLOY_ARTIFACT_MIME"));
            metadata.setHash(readOptionalEnv(env, "MVP_DEPLOY_ARTIFACT_HASH"));
            metadata.setDownloadUrl(readOptionalEnv(env, "MVP_DEPLOY_ARTIFACT_DOWNLOAD_URL"));
            metadata.setEntryPath(readOptionalEnv(env, "MVP_DEPLOY_ARTIFACT_ENTRY_PATH"));
            Long size = parsePositiveLong(readOptionalEnv(env, "MVP_DEPLOY_ARTIFACT_SIZE"));
            if (size != null) {
                metadata.setSize(size);
            }
            return metadata;
        }
        if (publishedArtifacts == null || publishedArtifacts.isEmpty()) {
            return null;
        }
        for (ArtifactMetadata artifact : publishedArtifacts) {
            if (artifact != null
                    && trimToNull(artifact.getArtifactId()) != null
                    && trimToNull(artifact.getType()) != null) {
                return artifact;
            }
        }
        return null;
    }

    private static ArtifactMetadata resolveDeployResultArtifact(Map<String, String> env) {
        String artifactId = readOptionalEnv(env, "MVP_DEPLOY_RESULT_ARTIFACT_ID");
        if (artifactId == null) {
            return null;
        }
        ArtifactMetadata metadata = new ArtifactMetadata();
        metadata.setArtifactId(artifactId);
        metadata.setType(firstNonBlank(
                readOptionalEnv(env, "MVP_DEPLOY_RESULT_ARTIFACT_TYPE"),
                "deploy_report"));
        metadata.setName(readOptionalEnv(env, "MVP_DEPLOY_RESULT_ARTIFACT_NAME"));
        metadata.setMime(readOptionalEnv(env, "MVP_DEPLOY_RESULT_ARTIFACT_MIME"));
        metadata.setHash(readOptionalEnv(env, "MVP_DEPLOY_RESULT_ARTIFACT_HASH"));
        metadata.setDownloadUrl(readOptionalEnv(env, "MVP_DEPLOY_RESULT_ARTIFACT_DOWNLOAD_URL"));
        metadata.setEntryPath(readOptionalEnv(env, "MVP_DEPLOY_RESULT_ARTIFACT_ENTRY_PATH"));
        Long size = parsePositiveLong(readOptionalEnv(env, "MVP_DEPLOY_RESULT_ARTIFACT_SIZE"));
        if (size != null) {
            metadata.setSize(size);
        }
        return metadata;
    }

    static Map<String, Object> buildDeployContext(
            TaskSummary task,
            String cwd,
            String requestId,
            ArtifactMetadata artifact,
            Map<String, String> env) {
        String action = firstNonBlank(readOptionalEnv(env, "MVP_DEPLOY_ACTION"), DEFAULT_DEPLOY_ACTION);
        String tool = firstNonBlank(readOptionalEnv(env, "MVP_DEPLOY_TOOL"), DEFAULT_DEPLOY_TOOL);
        String workspaceRef = normalizeWorkspaceRef(firstNonBlank(readOptionalEnv(env, "MVP_DEPLOY_WORKSPACE_REF"), cwd));
        String artifactId = artifact == null ? "" : firstNonBlank(artifact.getArtifactId(), "");
        String inputsHash = firstNonBlank(
                readOptionalEnv(env, "MVP_DEPLOY_INPUTS_HASH"),
                buildDeployInputsHash(task, requestId, workspaceRef, artifactId));

        HashMap<String, Object> context = new HashMap<>();
        context.put("action", action);
        context.put("tool", tool);
        context.put("workspaceRef", workspaceRef);
        context.put("inputsHash", inputsHash);
        return context;
    }

    static Map<String, Object> buildDeployApprovalPayload(
            String approvalId,
            String deployCommand,
            String cwd,
            Map<String, Object> context,
            long approvalTimeoutSeconds,
            Map<String, String> env) {
        HashMap<String, Object> payload = new HashMap<>();
        payload.put("approvalId", approvalId);
        payload.put("action", context.get("action"));
        payload.put("tool", context.get("tool"));
        payload.put("command", firstNonBlank(deployCommand, "deploy --dry-run"));
        payload.put("cwd", cwd);
        payload.put("approvalTimeoutSeconds", (int) Math.min(Integer.MAX_VALUE, approvalTimeoutSeconds));
        payload.put("riskScore", parseDoubleOrDefault(readOptionalEnv(env, "MVP_DEPLOY_APPROVAL_RISK_SCORE"), 0.95d));
        List<String> requiredPolicies = parseCsv(readOptionalEnv(env, "MVP_DEPLOY_REQUIRED_POLICIES"));
        if (requiredPolicies.isEmpty()) {
            requiredPolicies = List.of("approval.gate", "deploy.context.match");
        }
        payload.put("requiredPolicies", requiredPolicies);
        putIfNotBlank(payload, "toolVersion", readOptionalEnv(env, "MVP_DEPLOY_TOOL_VERSION"));
        payload.put("reason", firstNonBlank(readOptionalEnv(env, "MVP_DEPLOY_APPROVAL_REASON"), "deploy_gate"));
        payload.put("context", context);
        return payload;
    }

    static Map<String, Object> buildDeployPlanPayload(
            String requestId,
            String environment,
            ArtifactMetadata artifact,
            Map<String, Object> context,
            Map<String, String> env) {
        HashMap<String, Object> payload = new HashMap<>();
        payload.put("requestId", requestId);
        payload.put("environment", environment);
        payload.put("artifact", toArtifactPayload(artifact));
        putIfNotBlank(payload, "strategy", readOptionalEnv(env, "MVP_DEPLOY_STRATEGY"));
        putIfNotBlank(payload, "triggeredBy", readOptionalEnv(env, "MVP_DEPLOY_TRIGGERED_BY"));
        if (context != null && !context.isEmpty()) {
            payload.put("context", context);
        }
        String provider = readOptionalEnv(env, "MVP_DEPLOY_OPTION_PROVIDER");
        String project = readOptionalEnv(env, "MVP_DEPLOY_OPTION_PROJECT");
        if (provider != null || project != null) {
            HashMap<String, Object> options = new HashMap<>();
            putIfNotBlank(options, "provider", provider);
            putIfNotBlank(options, "project", project);
            if (!options.isEmpty()) {
                payload.put("options", options);
            }
        }
        return payload;
    }

    static Map<String, Object> buildDeployResultPayload(
            String requestId,
            String environment,
            String status,
            String message,
            Map<String, String> env,
            ArtifactMetadata resultArtifact,
            Instant startedAt,
            Instant finishedAt) {
        HashMap<String, Object> payload = new HashMap<>();
        payload.put("requestId", requestId);
        payload.put("status", status);
        putIfNotBlank(payload, "environment", environment);
        putIfNotBlank(payload, "message", message);
        putIfNotBlank(payload, "deploymentId", firstNonBlank(
                readOptionalEnv(env, "MVP_DEPLOY_DEPLOYMENT_ID"),
                "dep_" + UUID.randomUUID().toString().replace("-", "")));
        putIfNotBlank(payload, "endpointUrl", readOptionalEnv(env, "MVP_DEPLOY_ENDPOINT_URL"));
        if (startedAt != null) {
            payload.put("startedAt", startedAt.toString());
        }
        if (finishedAt != null) {
            payload.put("finishedAt", finishedAt.toString());
        }
        if (resultArtifact != null) {
            payload.put("resultArtifact", toArtifactPayload(resultArtifact));
        }
        return payload;
    }

    private static Map<String, Object> toArtifactPayload(ArtifactMetadata metadata) {
        Map<String, Object> payload = ArtifactReadyPayloads.fromMetadata(metadata);
        Object artifact = payload.get("artifact");
        if (artifact instanceof Map<?, ?> map) {
            @SuppressWarnings("unchecked")
            Map<String, Object> cast = (Map<String, Object>) map;
            return cast;
        }
        throw new IllegalArgumentException("artifact payload conversion failed");
    }

    private static String buildDeployInputsHash(
            TaskSummary task,
            String requestId,
            String workspaceRef,
            String artifactId) {
        TreeMap<String, String> normalized = new TreeMap<>();
        normalized.put("taskId", nz(task == null ? null : task.getTaskId()));
        normalized.put("projectId", nz(task == null ? null : task.getProjectId()));
        normalized.put("requestId", nz(requestId));
        normalized.put("workspaceRef", normalizeWorkspaceRef(workspaceRef));
        normalized.put("artifactId", nz(artifactId));
        normalized.put("prompt", nz(task == null ? null : task.getPrompt()));
        try {
            byte[] json = JSON.writeValueAsString(normalized).getBytes(StandardCharsets.UTF_8);
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(json);
            return "sha256:" + HexFormat.of().formatHex(digest);
        } catch (Exception ex) {
            throw new IllegalStateException("deployInputsHash", ex);
        }
    }

    private static String nz(String value) {
        return value == null ? "" : value;
    }

    private static String normalizeWorkspaceRef(String value) {
        String normalized = trimToNull(value);
        if (normalized == null) {
            return "";
        }
        return normalized.replace('\\', '/');
    }

    private static void putIfNotBlank(Map<String, Object> target, String key, String value) {
        String normalized = trimToNull(value);
        if (normalized != null) {
            target.put(key, normalized);
        }
    }

    private static Long parsePositiveLong(String raw) {
        if (raw == null) {
            return null;
        }
        try {
            long value = Long.parseLong(raw.trim());
            return value > 0 ? value : null;
        } catch (NumberFormatException ex) {
            return null;
        }
    }

    private static long parseLongOrDefault(String raw, long fallback) {
        if (raw == null) {
            return fallback;
        }
        try {
            long value = Long.parseLong(raw.trim());
            return value > 0 ? value : fallback;
        } catch (NumberFormatException ex) {
            return fallback;
        }
    }

    private static double parseDoubleOrDefault(String raw, double fallback) {
        if (raw == null) {
            return fallback;
        }
        try {
            double value = Double.parseDouble(raw.trim());
            return value >= 0 ? value : fallback;
        } catch (NumberFormatException ex) {
            return fallback;
        }
    }

    private static boolean isTruthyOrDefault(String raw, boolean fallback) {
        if (raw == null) {
            return fallback;
        }
        return isTruthy(raw);
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

        List<ServiceRuntimeDescriptor.PortBinding> portBindings = RuntimeSignalParser.parsePortBindings(env);
        if (portBindings.isEmpty()) {
            Integer port = RuntimeSignalParser.parsePositivePort(readOptionalEnv(env, "MVP_RUNTIME_PORT"));
            if (port != null) {
                ServiceRuntimeDescriptor.PortBinding binding = new ServiceRuntimeDescriptor.PortBinding();
                binding.setName(firstNonBlank(readOptionalEnv(env, "MVP_RUNTIME_PORT_NAME"), "http"));
                binding.setProtocol(firstNonBlank(readOptionalEnv(env, "MVP_RUNTIME_PORT_PROTOCOL"), "http"));
                binding.setPort(port);
                portBindings = List.of(binding);
            }
        }
        if (!portBindings.isEmpty()) {
            descriptor.setPorts(portBindings);
        }

        String healthPath = RuntimeSignalParser.normalizeHealthPath(readOptionalEnv(env, "MVP_RUNTIME_HEALTH_PATH"));
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
        List<ServiceRuntimeDescriptor.EnvVarSpec> environment = parseRuntimeEnvironmentSpecs(env);
        if (!environment.isEmpty()) {
            descriptor.setEnvironment(environment);
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
            String healthPath = RuntimeSignalParser.normalizeHealthPath(readOptionalEnv(env, "MVP_RUNTIME_HEALTH_PATH"));
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
                || readOptionalEnv(env, "MVP_RUNTIME_PORTS") != null
                || readOptionalEnv(env, "MVP_RUNTIME_HEALTH_PATH") != null
                || readOptionalEnv(env, "MVP_RUNTIME_HEALTH_URL") != null
                || readOptionalEnv(env, "MVP_RUNTIME_START_COMMAND") != null
                || readOptionalEnv(env, "MVP_RUNTIME_RUN_COMMAND") != null
                || readOptionalEnv(env, "MVP_RUNTIME_RUN_HINTS") != null
                || readOptionalEnv(env, "MVP_RUNTIME_ENV_SPECS") != null;
    }

    private static String buildHealthBaseUrl(Map<String, String> env) {
        Integer port = RuntimeSignalParser.resolvePrimaryRuntimePort(env);
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

    /**
     * Parses environment specs from {@code MVP_RUNTIME_ENV_SPECS}:
     * {@code NAME|required=true|default=dev|description=...;DB_URL|required=true}
     */
    private static List<ServiceRuntimeDescriptor.EnvVarSpec> parseRuntimeEnvironmentSpecs(Map<String, String> env) {
        String raw = readOptionalEnv(env, "MVP_RUNTIME_ENV_SPECS");
        if (raw == null) {
            return List.of();
        }
        ArrayList<ServiceRuntimeDescriptor.EnvVarSpec> specs = new ArrayList<>();
        for (String entryRaw : raw.split(";")) {
            String entry = trimToNull(entryRaw);
            if (entry == null) {
                continue;
            }
            ServiceRuntimeDescriptor.EnvVarSpec spec = new ServiceRuntimeDescriptor.EnvVarSpec();
            String[] tokens = entry.split("\\|");
            for (String tokenRaw : tokens) {
                String token = trimToNull(tokenRaw);
                if (token == null) {
                    continue;
                }
                int eq = token.indexOf('=');
                if (eq <= 0) {
                    if (spec.getName() == null) {
                        spec.setName(token);
                    }
                    continue;
                }
                String key = token.substring(0, eq).trim().toLowerCase(Locale.ROOT);
                String value = trimToNull(token.substring(eq + 1));
                if ("name".equals(key)) {
                    spec.setName(value);
                } else if ("required".equals(key)) {
                    spec.setRequired(value != null && isTruthy(value));
                } else if ("default".equals(key) || "defaultvalue".equals(key)) {
                    spec.setDefaultValue(value);
                } else if ("description".equals(key) || "desc".equals(key)) {
                    spec.setDescription(value);
                }
            }
            if (trimToNull(spec.getName()) != null) {
                specs.add(spec);
            }
        }
        return specs;
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
     * {@code ARTIFACT_READY} v1 JSON Schema allows only {@code artifact} and {@code kind} in payload - do not inject
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
