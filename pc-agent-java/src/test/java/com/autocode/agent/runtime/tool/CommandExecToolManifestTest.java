package com.autocode.agent.runtime.tool;

import com.autocode.agent.runtime.exec.CommandRunner;
import com.autocode.agent.runtime.tool.impl.CommandExecTool;
import com.autocode.agent.security.CommandSafetyPolicy;
import com.autocode.protocol.model.TaskSummary;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class CommandExecToolManifestTest {

    @Test
    void approvalPayloadIncludesManifestRiskAndPolicies() {
        CommandExecTool tool = new CommandExecTool(
                new CommandSafetyPolicy(List.of("echo"), false),
                new CommandRunner()
        );

        TaskSummary task = new TaskSummary();
        task.setTaskId("task_1");
        task.setAssistant("codex");

        ToolCall call = new ToolCall("command.exec", "run_command", Map.of(
                "command", "echo hello",
                "prompt", "print hello"
        ));
        ToolContext context = new ToolContext(task, "D:/workspace/task_1", "apr_1", 120);

        Map<String, Object> payload = tool.buildApprovalPayload(call, context);
        assertEquals("apr_1", payload.get("approvalId"));
        assertEquals("command.exec", payload.get("tool"));
        assertEquals("1.0.0", payload.get("toolVersion"));
        assertEquals(0.91d, payload.get("riskScore"));
        assertNotNull(payload.get("requiredPolicies"));
        @SuppressWarnings("unchecked")
        List<String> requiredPolicies = (List<String>) payload.get("requiredPolicies");
        assertTrue(requiredPolicies.contains("workspace.allowlist"));
        assertTrue(requiredPolicies.contains("approval.gate"));
    }
}
