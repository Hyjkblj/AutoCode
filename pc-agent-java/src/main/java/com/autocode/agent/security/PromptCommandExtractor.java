/**
 * Extracts an executable command string from a natural-language prompt (MVP heuristic).
 */
package com.autocode.agent.security;

public class PromptCommandExtractor {

    public String extractCommand(String prompt) {
        String lower = prompt.toLowerCase();
        int idx = lower.indexOf("exec ");
        if (idx < 0) {
            idx = lower.indexOf("command:");
            if (idx < 0) {
                return "git status";
            }
            return prompt.substring(idx + "command:".length()).trim();
        }
        return prompt.substring(idx + "exec ".length()).trim();
    }
}
