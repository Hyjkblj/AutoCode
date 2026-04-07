package com.autocode.agent.security.policy;

import com.autocode.agent.runtime.tool.ToolCall;
import com.autocode.agent.runtime.tool.ToolContext;
import com.autocode.protocol.model.TaskSummary;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class FileReadWritePolicyTest {

    @Test
    void allowsWriteWhenTargetPathIsUnderAllowlist() {
        FileReadWritePolicy policy = new FileReadWritePolicy(List.of("D:/repoA"));
        PolicyDecision decision = policy.evaluate(
                new ToolCall("command.exec", "run_command", Map.of("command", "rm -rf D:/repoA/tmp")),
                new ToolContext(new TaskSummary(), "D:/repoA", null, 120)
        );
        assertTrue(decision.isAllowed());
    }

    @Test
    void deniesWriteWhenTargetPathOutsideAllowlist() {
        FileReadWritePolicy policy = new FileReadWritePolicy(List.of("D:/repoA"));
        PolicyDecision decision = policy.evaluate(
                new ToolCall("command.exec", "run_command", Map.of("command", "del D:/repoB/output.txt")),
                new ToolContext(new TaskSummary(), "D:/repoA", null, 120)
        );
        assertFalse(decision.isAllowed());
        assertTrue("write_path_not_allowed".equals(decision.getReason()));
    }

    @Test
    void allowsWhenAllowlistIsEmptyForBackwardCompatibility() {
        FileReadWritePolicy policy = new FileReadWritePolicy(List.of());
        PolicyDecision decision = policy.evaluate(
                new ToolCall("command.exec", "run_command", Map.of("command", "del D:/anywhere/output.txt")),
                new ToolContext(new TaskSummary(), "D:/repoA", null, 120)
        );
        assertTrue(decision.isAllowed());
    }
}

