package com.autocode.agent.security.policy;

import com.autocode.agent.runtime.tool.ToolCall;
import com.autocode.agent.runtime.tool.ToolContext;

import java.util.ArrayList;
import java.util.List;

/**
 * Applies policies in order; first deny wins.
 */
public class CompositeToolInvocationPolicy implements ToolInvocationPolicy {
    private final List<ToolInvocationPolicy> policies;

    public CompositeToolInvocationPolicy(List<ToolInvocationPolicy> policies) {
        this.policies = policies == null ? List.of() : List.copyOf(policies);
    }

    public static Builder builder() {
        return new Builder();
    }

    @Override
    public PolicyDecision evaluate(ToolCall call, ToolContext context) {
        for (ToolInvocationPolicy p : policies) {
            PolicyDecision decision = p.evaluate(call, context);
            if (!decision.isAllowed()) {
                return decision;
            }
        }
        return PolicyDecision.allow();
    }

    public static class Builder {
        private final List<ToolInvocationPolicy> policies = new ArrayList<>();

        public Builder add(ToolInvocationPolicy policy) {
            if (policy != null) {
                policies.add(policy);
            }
            return this;
        }

        public CompositeToolInvocationPolicy build() {
            return new CompositeToolInvocationPolicy(policies);
        }
    }
}

