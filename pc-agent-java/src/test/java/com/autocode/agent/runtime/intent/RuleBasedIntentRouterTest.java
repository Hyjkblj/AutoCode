package com.autocode.agent.runtime.intent;

import com.autocode.agent.config.AgentConfig;
import com.autocode.protocol.model.TaskSummary;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class RuleBasedIntentRouterTest {

    @Test
    void routesByTaskProfileBeforeKeywordRules() {
        List<AgentConfig.IntentRule> rules = List.of(
                new AgentConfig.IntentRule(
                        "coder",
                        List.of(),
                        "skill.code.author",
                        "command.exec",
                        "run_command",
                        "mvn -q test"),
                new AgentConfig.IntentRule(
                        null,
                        List.of("deploy"),
                        "skill.deploy.pipeline",
                        "command.exec",
                        "run_command",
                        "echo deploy"));
        RuleBasedIntentRouter router = new RuleBasedIntentRouter(rules, "web");

        TaskSummary task = new TaskSummary();
        task.setAgentProfile("coder");
        task.setPrompt("please deploy service");

        RoutedIntent routed = router.route(task);

        assertEquals("skill.code.author", routed.skill());
        assertEquals("mvn -q test", routed.command());
        assertTrue(routed.routeSource().startsWith("profile:"));
    }

    @Test
    void routesByPromptKeywordWhenProfileDoesNotMatch() {
        List<AgentConfig.IntentRule> rules = List.of(
                new AgentConfig.IntentRule(
                        null,
                        List.of("deploy", "release"),
                        "skill.deploy.pipeline",
                        "command.exec",
                        "run_command",
                        "echo deploy"));
        RuleBasedIntentRouter router = new RuleBasedIntentRouter(rules, "coder");

        TaskSummary task = new TaskSummary();
        task.setAgentProfile("web");
        task.setPrompt("Need to DEPLOY build to staging");

        RoutedIntent routed = router.route(task);

        assertEquals("skill.deploy.pipeline", routed.skill());
        assertEquals("echo deploy", routed.command());
        assertTrue(routed.routeSource().startsWith("keyword:deploy"));
    }

    @Test
    void fallsBackToCommandExecWhenNoRuleMatches() {
        List<AgentConfig.IntentRule> rules = List.of(
                new AgentConfig.IntentRule("reviewer", List.of(), "skill.review", null, null, null));
        RuleBasedIntentRouter router = new RuleBasedIntentRouter(rules, "coder");

        TaskSummary task = new TaskSummary();
        task.setAgentProfile("coder");
        task.setPrompt("exec git diff");

        RoutedIntent routed = router.route(task);

        assertEquals("command.exec", routed.tool());
        assertEquals("run_command", routed.action());
        assertEquals("git diff", routed.command());
        assertEquals("fallback", routed.routeSource());
    }
}

