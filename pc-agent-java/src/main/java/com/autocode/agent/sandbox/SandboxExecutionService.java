package com.autocode.agent.sandbox;

import com.autocode.agent.client.AgentApiClient;
import com.autocode.agent.config.AgentConfig;
import com.autocode.agent.runtime.tool.Tool;
import com.autocode.agent.runtime.tool.ToolCall;
import com.autocode.agent.runtime.tool.ToolContext;
import com.autocode.agent.runtime.tool.ToolExecutionResult;
import com.autocode.agent.runtime.tool.ToolRegistry;
import com.autocode.agent.runtime.tool.impl.CommandExecTool;
import com.autocode.agent.security.CommandSafetyPolicy;
import com.autocode.agent.security.policy.CompositeToolInvocationPolicy;
import com.autocode.agent.security.policy.ElevationDetectionPolicy;
import com.autocode.agent.security.policy.EnvVarAccessPolicy;
import com.autocode.agent.security.policy.FileReadWritePolicy;
import com.autocode.agent.security.policy.NetworkAccessPolicy;
import com.autocode.agent.security.policy.PolicyDecision;
import com.autocode.agent.security.policy.WorkspaceAllowlistPolicy;
import com.autocode.protocol.model.ApprovalDecision;
import com.autocode.protocol.model.EventType;
import com.autocode.protocol.model.SandboxExecuteRequest;
import com.autocode.protocol.model.SandboxExecuteResponse;
import com.autocode.protocol.model.TaskEvent;
import com.autocode.protocol.model.TaskSummary;
import com.autocode.protocol.model.ToolManifest;
import com.autocode.protocol.model.ToolParamSpec;
import com.autocode.protocol.model.ToolPermissions;
import com.autocode.protocol.validation.ContractViolationException;
import com.autocode.protocol.validation.SandboxExecuteContractValidator;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Executes sandbox requests while preserving Java-side policy checks and approval gate semantics.
 */
public class SandboxExecutionService {
    private static final Logger log = LoggerFactory.getLogger(SandboxExecutionService.class);
    private static final String COMMAND_EXEC_TOOL_NAME = "command.exec";
    private static final String DEPLOY_EXEC_TOOL_NAME = "deploy.execute";

    private final AgentApiClient apiClient;
    private final AgentConfig config;
    private final ToolRegistry toolRegistry;
    private final CompositeToolInvocationPolicy invocationPolicy;
    private final AtomicLong seq = new AtomicLong(0);

    public SandboxExecutionService(AgentApiClient apiClient, AgentConfig config) {
        this.apiClient = Objects.requireNonNull(apiClient, "apiClient");
        this.config = Objects.requireNonNull(config, "config");
        this.toolRegistry = new ToolRegistry().register(new CommandExecTool(
                new CommandSafetyPolicy(config.getAllowedCommandPrefixes(), config.isNetworkAllowed()),
                new com.autocode.agent.runtime.exec.CommandRunner()
        ));
        this.invocationPolicy = CompositeToolInvocationPolicy.builder()
                .add(new ElevationDetectionPolicy())
                .add(new EnvVarAccessPolicy())
                .add(new NetworkAccessPolicy(config.isNetworkAllowed()))
                .add(new FileReadWritePolicy(config.getAllowedWorkspacePrefixes()))
                .add(new WorkspaceAllowlistPolicy(config.getAllowedWorkspacePrefixes()))
                .build();
    }

    public SandboxExecuteResponse execute(SandboxExecuteRequest request) throws IOException, InterruptedException {
        validateRequest(request);

        String toolName = firstNonBlank(request.getTool(), COMMAND_EXEC_TOOL_NAME);
        String registeredToolName = resolveRegisteredToolName(toolName);
        String action = firstNonBlank(request.getAction(), "run_command");
        String command = request.getCommand().trim();
        String cwd = firstNonBlank(request.getCwd(), System.getProperty("user.dir", ""));
        String traceId = firstNonBlank(request.getTraceId(), "trc_" + request.getTaskId());
        String runId = firstNonBlank(request.getRunId(), "run_" + UUID.randomUUID().toString().replace("-", ""));
        long approvalTimeoutSeconds = request.getApprovalTimeoutSeconds() != null && request.getApprovalTimeoutSeconds() > 0
                ? request.getApprovalTimeoutSeconds()
                : config.getApprovalTimeoutSeconds();

        TaskSummary task = toTaskSummary(request);
        ToolCall call = new ToolCall(
                toolName,
                action,
                request.getToolVersion() == null || request.getToolVersion().isBlank()
                        ? Map.of("command", command, "prompt", nz(request.getPrompt()))
                        : Map.of("command", command, "prompt", nz(request.getPrompt()), "toolVersion", request.getToolVersion())
        );

        Tool tool;
        try {
            tool = toolRegistry.getRequired(registeredToolName, request.getToolVersion());
        } catch (IllegalArgumentException ex) {
            return validatedResponse(SandboxExecuteResponse.failure(
                    "unknown_tool",
                    ex.getMessage(),
                    false,
                    toolName,
                    request.getToolVersion(),
                    traceId,
                    runId,
                    null
            ));
        }

        String resolvedToolVersion = trimToNull(tool.version());
        ToolContext preContext = new ToolContext(task, cwd, null, approvalTimeoutSeconds);
        PolicyDecision policyDecision = invocationPolicy.evaluate(call, preContext);
        if (!policyDecision.isAllowed()) {
            return validatedResponse(SandboxExecuteResponse.failure(
                    "denied",
                    "policy_denied:" + policyDecision.getReason(),
                    false,
                    toolName,
                    resolvedToolVersion,
                    traceId,
                    runId,
                    null
            ));
        }
        if (!tool.policy().isAllowed(call)) {
            return validatedResponse(SandboxExecuteResponse.failure(
                    "denied",
                    "command_not_allowed",
                    false,
                    toolName,
                    resolvedToolVersion,
                    traceId,
                    runId,
                    null
            ));
        }

        String approvalId = null;
        if (tool.policy().requiresApproval(call)) {
            approvalId = "apr_" + UUID.randomUUID().toString().replace("-", "");
            ToolContext approvalContext = new ToolContext(task, cwd, approvalId, approvalTimeoutSeconds);
            HashMap<String, Object> approvalPayload = new HashMap<>(tool.buildApprovalPayload(call, approvalContext));
            approvalPayload.put("tool", toolName);
            if (resolvedToolVersion != null) {
                approvalPayload.put("toolVersion", resolvedToolVersion);
            }
            publishEvent(task, traceId, runId, EventType.APPROVAL_REQUIRED, approvalPayload);

            ApprovalDecision decision = waitForApproval(request.getTaskId(), approvalTimeoutSeconds);
            publishEvent(task, traceId, runId, EventType.APPROVAL_RESULT, Map.of(
                    "approvalId", approvalId,
                    "decision", decision.name().toLowerCase()
            ));
            if (decision == ApprovalDecision.REJECT) {
                return validatedResponse(SandboxExecuteResponse.failure(
                        "approval_rejected",
                        "approval_rejected",
                        false,
                        toolName,
                        resolvedToolVersion,
                        traceId,
                        runId,
                        approvalId
                ));
            }
            if (decision == ApprovalDecision.PENDING) {
                return validatedResponse(SandboxExecuteResponse.failure(
                        "approval_timeout",
                        "approval_timeout",
                        true,
                        toolName,
                        resolvedToolVersion,
                        traceId,
                        runId,
                        approvalId
                ));
            }
        }

        HashMap<String, Object> toolStart = new HashMap<>();
        toolStart.put("tool", toolName);
        toolStart.put("action", action);
        toolStart.put("command", command);
        toolStart.put("cwd", cwd);
        toolStart.put("workspaceRef", normalizeWorkspaceRef(cwd));
        if (resolvedToolVersion != null) {
            toolStart.put("toolVersion", resolvedToolVersion);
        }
        if (approvalId != null) {
            toolStart.put("approvalId", approvalId);
        }
        publishEvent(task, traceId, runId, EventType.TOOL_START, toolStart);

        ToolExecutionResult executionResult;
        try {
            executionResult = tool.execute(call, new ToolContext(task, cwd, approvalId, approvalTimeoutSeconds));
        } catch (Exception ex) {
            HashMap<String, Object> errorPayload = new HashMap<>();
            errorPayload.put("tool", toolName);
            errorPayload.put("status", "error");
            errorPayload.put("error", ex.getMessage() == null ? "exec_error" : ex.getMessage());
            if (resolvedToolVersion != null) {
                errorPayload.put("toolVersion", resolvedToolVersion);
            }
            publishEvent(task, traceId, runId, EventType.TOOL_END, errorPayload);
            return validatedResponse(SandboxExecuteResponse.failure(
                    "error",
                    ex.getMessage() == null ? "exec_error" : ex.getMessage(),
                    false,
                    toolName,
                    resolvedToolVersion,
                    traceId,
                    runId,
                    approvalId
            ));
        }

        HashMap<String, Object> toolEnd = new HashMap<>(executionResult.getToolEndPayload());
        toolEnd.put("tool", toolName);
        if (resolvedToolVersion != null) {
            toolEnd.put("toolVersion", resolvedToolVersion);
        }
        publishEvent(task, traceId, runId, EventType.TOOL_END, toolEnd);

        Integer exitCode = asInteger(toolEnd.get("exitCode"));
        String output = asString(toolEnd.get("output"));
        String status = firstNonBlank(asString(toolEnd.get("status")), executionResult.isSuccess() ? "ok" : "failed");
        if (executionResult.isSuccess()) {
            return validatedResponse(SandboxExecuteResponse.success(
                    status,
                    exitCode,
                    output,
                    executionResult.isRetryable(),
                    toolName,
                    resolvedToolVersion,
                    traceId,
                    runId
            ));
        }
        return validatedResponse(SandboxExecuteResponse.failure(
                status,
                firstNonBlank(asString(toolEnd.get("error")), "tool_failed"),
                executionResult.isRetryable(),
                toolName,
                resolvedToolVersion,
                traceId,
                runId,
                approvalId
        ));
    }

    public List<ToolManifest> listToolManifests() {
        ArrayList<ToolManifest> manifests = new ArrayList<>(toolRegistry.listManifests());
        if (!containsToolManifest(manifests, DEPLOY_EXEC_TOOL_NAME)) {
            ToolManifest commandExec = findToolManifest(manifests, COMMAND_EXEC_TOOL_NAME);
            if (commandExec != null) {
                manifests.add(copyToolManifestWithAlias(
                        commandExec,
                        DEPLOY_EXEC_TOOL_NAME,
                        "Execute deployment command under sandbox policy constraints."));
            }
        }
        return List.copyOf(manifests);
    }

    private void publishEvent(
            TaskSummary task,
            String traceId,
            String runId,
            EventType type,
            Map<String, Object> payload) throws IOException {
        HashMap<String, Object> mergedPayload = new HashMap<>();
        mergedPayload.put("traceId", traceId);
        mergedPayload.put("runId", runId);
        if (payload != null) {
            mergedPayload.putAll(payload);
        }
        TaskEvent event = new TaskEvent();
        event.setEventId("evt_" + UUID.randomUUID().toString().replace("-", ""));
        event.setEventVersion(1);
        event.setType(type);
        event.setTimestamp(Instant.now());
        event.setTaskId(task.getTaskId());
        event.setAssistant(task.getAssistant());
        String sessionId = firstNonBlank(task.getSessionId(), task.getSessionKey());
        if (sessionId != null) {
            event.setSessionId(sessionId);
        }
        event.setSeq(seq.getAndIncrement());
        event.setPayload(mergedPayload);
        apiClient.publishEvent(task.getTaskId(), event);
    }

    private ApprovalDecision waitForApproval(String taskId, long timeoutSeconds) throws IOException, InterruptedException {
        long deadline = System.currentTimeMillis() + Math.max(1, timeoutSeconds) * 1000L;
        while (System.currentTimeMillis() < deadline) {
            ApprovalDecision decision = apiClient.getApprovalDecision(taskId);
            if (decision == ApprovalDecision.APPROVE || decision == ApprovalDecision.REJECT) {
                return decision;
            }
            Thread.sleep(2000L);
        }
        return ApprovalDecision.PENDING;
    }

    private static TaskSummary toTaskSummary(SandboxExecuteRequest request) {
        TaskSummary task = new TaskSummary();
        task.setTaskId(request.getTaskId());
        task.setPrompt(trimToNull(request.getPrompt()));
        task.setAssistant(firstNonBlank(request.getAssistant(), "python-agent"));
        task.setSessionId(trimToNull(request.getSessionId()));
        task.setSessionKey(trimToNull(request.getSessionKey()));
        task.setWorkspacePath(trimToNull(request.getCwd()));
        return task;
    }

    private static void validateRequest(SandboxExecuteRequest request) {
        try {
            SandboxExecuteContractValidator.validateRequest(request);
        } catch (ContractViolationException ex) {
            throw new IllegalArgumentException(ex.getMessage(), ex);
        }
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

    private static String nz(String value) {
        return value == null ? "" : value;
    }

    private static String trimToNull(String value) {
        if (value == null) {
            return null;
        }
        String trimmed = value.trim();
        return trimmed.isEmpty() ? null : trimmed;
    }

    private static Integer asInteger(Object value) {
        if (value instanceof Number number) {
            return number.intValue();
        }
        if (value instanceof String s) {
            try {
                return Integer.parseInt(s.trim());
            } catch (NumberFormatException ignored) {
                return null;
            }
        }
        return null;
    }

    private static String asString(Object value) {
        if (value == null) {
            return null;
        }
        return String.valueOf(value);
    }

    private static SandboxExecuteResponse validatedResponse(SandboxExecuteResponse response) {
        try {
            SandboxExecuteContractValidator.validateResponse(response);
            return response;
        } catch (ContractViolationException ex) {
            throw new IllegalStateException("sandbox execute response contract violation: " + ex.getMessage(), ex);
        }
    }

    private static String normalizeWorkspaceRef(String value) {
        String normalized = trimToNull(value);
        if (normalized == null) {
            return "";
        }
        return normalized.replace('\\', '/');
    }

    private static String resolveRegisteredToolName(String requestedToolName) {
        if (DEPLOY_EXEC_TOOL_NAME.equals(requestedToolName)) {
            return COMMAND_EXEC_TOOL_NAME;
        }
        return requestedToolName;
    }

    private static boolean containsToolManifest(List<ToolManifest> manifests, String name) {
        return findToolManifest(manifests, name) != null;
    }

    private static ToolManifest findToolManifest(List<ToolManifest> manifests, String name) {
        if (manifests == null || name == null) {
            return null;
        }
        for (ToolManifest manifest : manifests) {
            if (manifest != null && name.equals(trimToNull(manifest.getName()))) {
                return manifest;
            }
        }
        return null;
    }

    private static ToolManifest copyToolManifestWithAlias(ToolManifest source, String aliasName, String aliasDescription) {
        ToolManifest copy = new ToolManifest();
        copy.setName(aliasName);
        copy.setVersion(source.getVersion());
        copy.setDescription(aliasDescription);
        copy.setAction(source.getAction());
        if (source.getArgsSchema() != null) {
            copy.setArgsSchema(new HashMap<>(source.getArgsSchema()));
        }

        ArrayList<ToolParamSpec> params = new ArrayList<>();
        if (source.getParams() != null) {
            for (ToolParamSpec param : source.getParams()) {
                if (param == null) {
                    continue;
                }
                ToolParamSpec paramCopy = new ToolParamSpec();
                paramCopy.setName(param.getName());
                paramCopy.setType(param.getType());
                paramCopy.setRequired(param.isRequired());
                paramCopy.setDescription(param.getDescription());
                paramCopy.setDefaultValue(param.getDefaultValue());
                if (param.getEnumValues() != null) {
                    paramCopy.setEnumValues(new ArrayList<>(param.getEnumValues()));
                }
                params.add(paramCopy);
            }
        }
        copy.setParams(params);

        if (source.getPermissions() != null) {
            ToolPermissions permissionsCopy = new ToolPermissions();
            ToolPermissions sourcePermissions = source.getPermissions();
            permissionsCopy.setCommandExec(sourcePermissions.isCommandExec());
            permissionsCopy.setFileRead(sourcePermissions.isFileRead());
            permissionsCopy.setFileWrite(sourcePermissions.isFileWrite());
            permissionsCopy.setNetworkAccess(sourcePermissions.isNetworkAccess());
            permissionsCopy.setApprovalRequired(sourcePermissions.isApprovalRequired());
            permissionsCopy.setRiskScore(sourcePermissions.getRiskScore());
            if (sourcePermissions.getRequiredPolicies() != null) {
                permissionsCopy.setRequiredPolicies(new ArrayList<>(sourcePermissions.getRequiredPolicies()));
            }
            copy.setPermissions(permissionsCopy);
        }
        return copy;
    }
}
