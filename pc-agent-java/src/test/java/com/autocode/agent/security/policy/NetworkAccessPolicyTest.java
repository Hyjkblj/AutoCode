package com.autocode.agent.security.policy;

import com.autocode.agent.runtime.tool.ToolCall;
import com.autocode.agent.runtime.tool.ToolContext;
import com.autocode.protocol.model.TaskSummary;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class NetworkAccessPolicyTest {

    @Test
    void deniesNetworkCommandWhenNetworkDisabled() {
        NetworkAccessPolicy policy = new NetworkAccessPolicy(false);
        PolicyDecision decision = policy.evaluate(
                new ToolCall("command.exec", "run_command", Map.of("command", "curl https://example.com")),
                new ToolContext(new TaskSummary(), "D:/repo", null, 120)
        );
        assertFalse(decision.isAllowed());
        assertTrue("network_not_allowed".equals(decision.getReason()));
    }

    @Test
    void allowsNetworkCommandWhenNetworkEnabled() {
        NetworkAccessPolicy policy = new NetworkAccessPolicy(true);
        PolicyDecision decision = policy.evaluate(
                new ToolCall("command.exec", "run_command", Map.of("command", "curl https://example.com")),
                new ToolContext(new TaskSummary(), "D:/repo", null, 120)
        );
        assertTrue(decision.isAllowed());
    }
}

