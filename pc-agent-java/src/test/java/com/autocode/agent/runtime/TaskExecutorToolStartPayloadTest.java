package com.autocode.agent.runtime;

import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;

class TaskExecutorToolStartPayloadTest {

    @Test
    void buildToolStartPayloadIncludesNormalizedWorkspaceRef() {
        Map<String, Object> payload = TaskExecutor.buildToolStartPayload(
                "command.exec",
                "1.0.0",
                "echo hello",
                "D:\\workspace\\task-1",
                "run_command",
                "skill.code.execute",
                "intent.router",
                "apr_1"
        );

        assertEquals("D:\\workspace\\task-1", payload.get("cwd"));
        assertEquals("D:/workspace/task-1", payload.get("workspaceRef"));
        assertEquals("apr_1", payload.get("approvalId"));
        assertEquals("1.0.0", payload.get("toolVersion"));
    }

    @Test
    void buildToolStartPayloadSkipsBlankOptionalFields() {
        Map<String, Object> payload = TaskExecutor.buildToolStartPayload(
                "command.exec",
                "   ",
                "echo hello",
                "D:/workspace/task-1",
                "run_command",
                "skill.code.execute",
                "intent.router",
                null
        );

        assertEquals("D:/workspace/task-1", payload.get("workspaceRef"));
        assertFalse(payload.containsKey("toolVersion"));
        assertFalse(payload.containsKey("approvalId"));
    }
}
