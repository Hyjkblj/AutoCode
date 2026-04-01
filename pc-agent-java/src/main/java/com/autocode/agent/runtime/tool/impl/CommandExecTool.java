package com.autocode.agent.runtime.tool.impl;

import com.autocode.agent.runtime.exec.CommandRunResult;
import com.autocode.agent.runtime.exec.CommandRunner;
import com.autocode.agent.security.CommandSafetyPolicy;
import com.autocode.agent.runtime.tool.Tool;
import com.autocode.agent.runtime.tool.ToolCall;
import com.autocode.agent.runtime.tool.ToolContext;
import com.autocode.agent.runtime.tool.ToolExecutionResult;
import com.autocode.agent.runtime.tool.ToolPolicy;
import com.autocode.protocol.model.TaskSummary;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Duration;
import java.util.HashMap;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;
import java.util.TreeMap;

/**
 * Built-in command execution tool (MVP).
 */
public class CommandExecTool implements Tool {
    public static final String NAME = "command.exec";

    private static final ObjectMapper APPROVAL_INPUTS_JSON = new ObjectMapper()
            .enable(SerializationFeature.ORDER_MAP_ENTRIES_BY_KEYS);

    private final CommandSafetyPolicy safetyPolicy;
    private final CommandRunner runner;

    public CommandExecTool(CommandSafetyPolicy safetyPolicy, CommandRunner runner) {
        this.safetyPolicy = safetyPolicy;
        this.runner = runner;
    }

    @Override
    public String name() {
        return NAME;
    }

    @Override
    public ToolPolicy policy() {
        return new ToolPolicy() {
            @Override
            public boolean isAllowed(ToolCall call) {
                String command = String.valueOf(call.getArgs().getOrDefault("command", ""));
                return safetyPolicy.isAllowed(command);
            }

            @Override
            public boolean requiresApproval(ToolCall call) {
                String command = String.valueOf(call.getArgs().getOrDefault("command", ""));
                String prompt = String.valueOf(call.getArgs().getOrDefault("prompt", ""));
                return safetyPolicy.requiresApproval(prompt, command);
            }
        };
    }

    @Override
    public Map<String, Object> buildApprovalPayload(ToolCall call, ToolContext context) {
        String command = String.valueOf(call.getArgs().getOrDefault("command", ""));
        String cwd = context.getCwd() == null ? "" : context.getCwd();
        TaskSummary task = context.getTask();

        Map<String, Object> body = new HashMap<>();
        body.put("approvalId", context.getApprovalId());
        body.put("action", call.getAction());
        body.put("command", command);
        body.put("tool", NAME);
        body.put("cwd", cwd);
        body.put("approvalTimeoutSeconds", (int) Math.min(Integer.MAX_VALUE, context.getApprovalTimeoutSeconds()));
        body.put("riskScore", 0.91);
        body.put("reason", "network_and_remote_write");

        Map<String, String> ctx = new LinkedHashMap<>();
        ctx.put("action", "app.generate");
        ctx.put("tool", catalogToolForAssistant(task));
        ctx.put("workspaceRef", cwd);
        ctx.put("inputsHash", approvalInputsHash(task, cwd));
        body.put("context", ctx);
        return body;
    }

    /**
     * Matches Python runner {@code _approval_inputs_hash} shape: sorted keys, empty {@code specDigest} until a spec
     * file exists on the node.
     */
    private static String approvalInputsHash(TaskSummary task, String cwd) {
        TreeMap<String, String> m = new TreeMap<>();
        m.put("projectId", nz(task == null ? null : task.getProjectId()));
        m.put("prompt", nz(task == null ? null : task.getPrompt()));
        m.put("specDigest", "");
        m.put("taskId", nz(task == null ? null : task.getTaskId()));
        m.put("workspacePath", normalizeWorkspacePath(cwd));
        try {
            String json = APPROVAL_INPUTS_JSON.writeValueAsString(m);
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] raw = digest.digest(json.getBytes(StandardCharsets.UTF_8));
            return "sha256:" + HexFormat.of().formatHex(raw);
        } catch (Exception e) {
            throw new IllegalStateException("approvalInputsHash", e);
        }
    }

    private static String nz(String s) {
        return s == null ? "" : s;
    }

    private static String normalizeWorkspacePath(String cwd) {
        return cwd.replace('\\', '/').trim();
    }

    private static String catalogToolForAssistant(TaskSummary task) {
        if (task != null && task.getAssistant() != null
                && task.getAssistant().toLowerCase(Locale.ROOT).contains("codex")) {
            return "claudecode.run";
        }
        return "build.run";
    }

    @Override
    public ToolExecutionResult execute(ToolCall call, ToolContext context) throws Exception {
        String command = String.valueOf(call.getArgs().getOrDefault("command", ""));
        CommandRunResult result = runner.run(command, Duration.ofSeconds(30), context.getCwd());

        Map<String, Object> toolEnd = Map.of(
                "tool", name(),
                "status", result.isTimedOut() ? "timeout" : "ok",
                "exitCode", result.getExitCode(),
                "output", result.getOutput()
        );

        boolean success = !result.isTimedOut() && result.getExitCode() == 0;
        boolean retryable = result.isTimedOut();
        return new ToolExecutionResult(toolEnd, success, retryable);
    }
}

