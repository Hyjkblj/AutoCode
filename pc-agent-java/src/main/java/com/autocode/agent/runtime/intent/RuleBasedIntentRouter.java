package com.autocode.agent.runtime.intent;

import com.autocode.agent.config.AgentConfig;
import com.autocode.agent.security.PromptCommandExtractor;
import com.autocode.protocol.model.TaskSummary;

import java.util.List;
import java.util.Locale;

/**
 * Routes tasks by profile and prompt keywords, then falls back to command.exec behavior.
 */
public class RuleBasedIntentRouter implements IntentRouter {
    private final List<AgentConfig.IntentRule> rules;
    private final String defaultProfile;
    private final PromptCommandExtractor promptCommandExtractor;

    public RuleBasedIntentRouter(List<AgentConfig.IntentRule> rules, String defaultProfile) {
        this.rules = rules == null ? List.of() : List.copyOf(rules);
        this.defaultProfile = normalize(defaultProfile);
        this.promptCommandExtractor = new PromptCommandExtractor();
    }

    @Override
    public RoutedIntent route(TaskSummary task) {
        String prompt = task == null || task.getPrompt() == null ? "" : task.getPrompt();
        String fallbackCommand = promptCommandExtractor.extractCommand(prompt);
        String profile = resolveProfile(task);
        String promptLower = prompt.toLowerCase(Locale.ROOT);

        for (AgentConfig.IntentRule rule : rules) {
            if (rule.matchesProfile(profile)) {
                return toIntent(rule, fallbackCommand, "profile:" + profile);
            }
        }
        for (AgentConfig.IntentRule rule : rules) {
            String matchedKeyword = rule.firstMatchedKeyword(promptLower);
            if (matchedKeyword != null) {
                return toIntent(rule, fallbackCommand, "keyword:" + matchedKeyword);
            }
        }
        return RoutedIntent.fallback(fallbackCommand);
    }

    private RoutedIntent toIntent(AgentConfig.IntentRule rule, String fallbackCommand, String routeSource) {
        String command = firstNonBlank(rule.command(), fallbackCommand);
        return new RoutedIntent(rule.tool(), rule.action(), rule.skill(), command, routeSource);
    }

    private String resolveProfile(TaskSummary task) {
        String fromTask = task == null ? null : normalize(task.getAgentProfile());
        return firstNonBlank(fromTask, defaultProfile, "");
    }

    private static String normalize(String value) {
        if (value == null) {
            return null;
        }
        String trimmed = value.trim();
        if (trimmed.isEmpty()) {
            return null;
        }
        return trimmed.toLowerCase(Locale.ROOT);
    }

    private static String firstNonBlank(String... values) {
        if (values == null) {
            return null;
        }
        for (String value : values) {
            if (value == null) {
                continue;
            }
            String trimmed = value.trim();
            if (!trimmed.isEmpty()) {
                return trimmed;
            }
        }
        return null;
    }
}

