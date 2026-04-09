package com.autocode.agent.runtime.tool.impl;

import com.autocode.agent.runtime.exec.CommandRunResult;
import com.autocode.agent.runtime.exec.CommandRunner;
import com.autocode.agent.security.CommandSafetyPolicy;
import com.autocode.agent.runtime.tool.Tool;
import com.autocode.agent.runtime.tool.ToolCall;
import com.autocode.agent.runtime.tool.ToolContext;
import com.autocode.agent.runtime.tool.ToolExecutionResult;
import com.autocode.agent.runtime.tool.ToolPolicy;
import com.autocode.protocol.model.ToolManifest;
import com.autocode.protocol.model.ToolParamSpec;
import com.autocode.protocol.model.ToolPermissions;
import com.autocode.protocol.model.TaskSummary;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Duration;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.TreeMap;

/**
 * Built-in command execution tool (MVP).
 */
public class CommandExecTool implements Tool {
    public static final String NAME = "command.exec";
    public static final String VERSION = "1.0.0";

    private static final ObjectMapper APPROVAL_INPUTS_JSON = new ObjectMapper()
            .enable(SerializationFeature.ORDER_MAP_ENTRIES_BY_KEYS);

    private final CommandSafetyPolicy safetyPolicy;
    private final CommandRunner runner;
    private final ToolManifest manifest;

    public CommandExecTool(CommandSafetyPolicy safetyPolicy, CommandRunner runner) {
        this.safetyPolicy = safetyPolicy;
        this.runner = runner;
        this.manifest = buildManifest();
    }

    @Override
    public ToolManifest manifest() {
        return manifest;
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
        ToolPermissions permissions = manifest.getPermissions();

        Map<String, Object> body = new HashMap<>();
        body.put("approvalId", context.getApprovalId());
        body.put("action", call.getAction());
        body.put("command", command);
        body.put("tool", NAME);
        body.put("toolVersion", VERSION);
        body.put("cwd", cwd);
        body.put("workspaceRef", normalizeWorkspacePath(cwd));
        body.put("approvalTimeoutSeconds", (int) Math.min(Integer.MAX_VALUE, context.getApprovalTimeoutSeconds()));
        body.put("riskScore", permissions == null ? 0.91 : permissions.getRiskScore());
        body.put("requiredPolicies", permissions == null ? List.of() : permissions.getRequiredPolicies());
        body.put("reason", "network_and_remote_write");

        Map<String, String> ctx = new LinkedHashMap<>();
        ctx.put("action", "app.generate");
        ctx.put("tool", catalogToolForAssistant(task));
        ctx.put("workspaceRef", normalizeWorkspacePath(cwd));
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

    private static ToolManifest buildManifest() {
        ToolManifest manifest = new ToolManifest();
        manifest.setName(NAME);
        manifest.setVersion(VERSION);
        manifest.setDescription("Execute a shell command under policy constraints.");
        manifest.setAction("run_command");
        manifest.setArgsSchema(Map.of(
                "type", "object",
                "required", List.of("command"),
                "properties", Map.of(
                        "command", Map.of("type", "string"),
                        "prompt", Map.of("type", "string"),
                        "toolVersion", Map.of("type", "string")
                )
        ));

        ArrayList<ToolParamSpec> params = new ArrayList<>();
        ToolParamSpec command = new ToolParamSpec();
        command.setName("command");
        command.setType("string");
        command.setRequired(true);
        command.setDescription("Command text to execute.");
        params.add(command);

        ToolParamSpec prompt = new ToolParamSpec();
        prompt.setName("prompt");
        prompt.setType("string");
        prompt.setRequired(false);
        prompt.setDescription("Original user prompt for policy context.");
        params.add(prompt);
        manifest.setParams(params);

        ToolPermissions permissions = new ToolPermissions();
        permissions.setCommandExec(true);
        permissions.setFileRead(true);
        permissions.setFileWrite(true);
        permissions.setNetworkAccess(false);
        permissions.setApprovalRequired(true);
        permissions.setRiskScore(0.91d);
        permissions.setRequiredPolicies(List.of(
                "workspace.allowlist",
                "command.safety",
                "approval.gate"
        ));
        manifest.setPermissions(permissions);
        return manifest;
    }
}

