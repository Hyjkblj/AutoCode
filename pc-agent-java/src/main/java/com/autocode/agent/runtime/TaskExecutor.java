/**
 * Task execution orchestrator on the node: policy checks, optional approval wait, then tool execution.
 */
package com.autocode.agent.runtime;

import com.autocode.agent.client.AgentApiClient;
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
import com.autocode.agent.security.PromptCommandExtractor;
import com.autocode.agent.security.policy.CompositeToolInvocationPolicy;
import com.autocode.agent.security.policy.PolicyDecision;
import com.autocode.agent.security.policy.WorkspaceAllowlistPolicy;
import com.autocode.protocol.model.ApprovalDecision;
import com.autocode.protocol.model.EventType;
import com.autocode.protocol.model.TaskEvent;
import com.autocode.protocol.model.TaskSummary;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.time.Instant;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

public class TaskExecutor {
    private static final Logger log = LoggerFactory.getLogger(TaskExecutor.class);

    private final AgentApiClient client;
    private final PromptCommandExtractor promptCommandExtractor;
    private volatile AgentConfig config;
    private final CommandRunner commandRunner;
    private final GitDiffCollector gitDiffCollector;
    private final ToolRegistry toolRegistry;
    private volatile CompositeToolInvocationPolicy invocationPolicy;

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
                .register(new CommandExecTool(new CommandSafetyPolicy(config.getAllowedCommandPrefixes()), this.commandRunner));
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
        String cwd = (task.getWorkspacePath() == null || task.getWorkspacePath().isBlank())
                ? System.getProperty("user.dir", "")
                : task.getWorkspacePath();
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
        send(task, traceId, runId, EventType.TOOL_START, Map.of(
                "tool", call.getTool(),
                "command", command,
                "cwd", cwd,
                "approvalId", approvalIdForExec,
                "action", call.getAction()
        ));

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

        long totalMs = (System.nanoTime() - taskStartNs) / 1_000_000;
        log.info("Task {} done total {}ms traceId={} runId={}", task.getTaskId(), totalMs, traceId, runId);
        send(task, traceId, runId, EventType.TASK_DONE, Map.of("result", "success"));
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
        TaskEvent event = new TaskEvent();
        event.setType(type);
        event.setTimestamp(Instant.now());
        event.setAssistant(task.getAssistant());
        HashMap<String, Object> merged = new HashMap<>();
        merged.put("traceId", traceId);
        merged.put("runId", runId);
        merged.putAll(payload);
        event.setPayload(merged);
        client.publishEvent(task.getTaskId(), event);
    }
}
