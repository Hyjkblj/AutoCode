package com.autocode.agent.security.policy;

import com.autocode.agent.runtime.tool.ToolCall;
import com.autocode.agent.runtime.tool.ToolContext;
import com.autocode.protocol.model.TaskSummary;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ElevationDetectionPolicyTest {

    @Test
    void deniesSudoCommand() {
        ElevationDetectionPolicy policy = new ElevationDetectionPolicy();
        PolicyDecision decision = policy.evaluate(
                new ToolCall("command.exec", "run_command", Map.of("command", "sudo rm -rf /tmp/demo")),
                new ToolContext(new TaskSummary(), "D:/repo", null, 120)
        );
        assertFalse(decision.isAllowed());
        assertTrue("elevation_not_allowed".equals(decision.getReason()));
    }

    @Test
    void allowsRegularCommand() {
        ElevationDetectionPolicy policy = new ElevationDetectionPolicy();
        PolicyDecision decision = policy.evaluate(
                new ToolCall("command.exec", "run_command", Map.of("command", "echo safe")),
                new ToolContext(new TaskSummary(), "D:/repo", null, 120)
        );
        assertTrue(decision.isAllowed());
    }
}

