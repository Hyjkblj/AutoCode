package com.autocode.agent.runtime.tool.impl;

import com.autocode.agent.runtime.exec.CommandRunResult;
import com.autocode.agent.runtime.exec.CommandRunner;
import com.autocode.agent.security.CommandSafetyPolicy;
import com.autocode.agent.runtime.tool.Tool;
import com.autocode.agent.runtime.tool.ToolCall;
import com.autocode.agent.runtime.tool.ToolContext;
import com.autocode.agent.runtime.tool.ToolExecutionResult;
import com.autocode.agent.runtime.tool.ToolPolicy;

import java.time.Duration;
import java.util.Map;

/**
 * Built-in command execution tool (MVP).
 */
public class CommandExecTool implements Tool {
    public static final String NAME = "command.exec";

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
        return Map.of(
                "approvalId", context.getApprovalId(),
                "action", call.getAction(),
                "command", command,
                "cwd", context.getCwd(),
                "approvalTimeoutSeconds", context.getApprovalTimeoutSeconds(),
                "riskScore", 0.91,
                "reason", "network_and_remote_write"
        );
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

