package com.autocode.agent.security.policy;

import com.autocode.agent.runtime.tool.ToolCall;
import com.autocode.agent.runtime.tool.ToolContext;
import com.autocode.protocol.model.TaskSummary;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class EnvVarAccessPolicyTest {

    @Test
    void deniesSensitiveEnvReference() {
        EnvVarAccessPolicy policy = new EnvVarAccessPolicy();
        PolicyDecision decision = policy.evaluate(
                new ToolCall("command.exec", "run_command", Map.of("command", "echo $OPENAI_API_KEY")),
                new ToolContext(new TaskSummary(), "D:/repo", null, 120)
        );
        assertFalse(decision.isAllowed());
        assertTrue("env_access_not_allowed".equals(decision.getReason()));
    }

    @Test
    void allowsCommandWithoutSensitiveEnvReference() {
        EnvVarAccessPolicy policy = new EnvVarAccessPolicy();
        PolicyDecision decision = policy.evaluate(
                new ToolCall("command.exec", "run_command", Map.of("command", "echo hello")),
                new ToolContext(new TaskSummary(), "D:/repo", null, 120)
        );
        assertTrue(decision.isAllowed());
    }
}

