package com.autocode.agent.security.policy;

import com.autocode.agent.runtime.tool.ToolCall;
import com.autocode.agent.runtime.tool.ToolContext;
import com.autocode.protocol.model.TaskSummary;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class WorkspaceAllowlistPolicyTest {
    @Test
    void emptyAllowlistAllowsAll() {
        WorkspaceAllowlistPolicy policy = new WorkspaceAllowlistPolicy(java.util.List.of());
        PolicyDecision d = policy.evaluate(
                new ToolCall("command.exec", "run_command", Map.of()),
                new ToolContext(new TaskSummary(), "D:/repo", null, 120)
        );
        assertTrue(d.isAllowed());
    }

    @Test
    void nonEmptyAllowlistDeniesOutside() {
        WorkspaceAllowlistPolicy policy = new WorkspaceAllowlistPolicy(java.util.List.of("D:/repoA"));
        PolicyDecision d = policy.evaluate(
                new ToolCall("command.exec", "run_command", Map.of()),
                new ToolContext(new TaskSummary(), "D:/repoB", null, 120)
        );
        assertFalse(d.isAllowed());
    }
}

