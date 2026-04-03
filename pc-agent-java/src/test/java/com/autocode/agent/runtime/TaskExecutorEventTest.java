package com.autocode.agent.runtime;

import com.autocode.protocol.model.EventType;
import com.autocode.protocol.model.TaskEvent;
import com.autocode.protocol.model.TaskSummary;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;

class TaskExecutorEventTest {

    @Test
    void buildEventSetsRequiredEnvelopeFields() {
        TaskSummary task = new TaskSummary();
        task.setTaskId("task_1");
        task.setAssistant("codex");
        task.setSessionId("sess_id_1");
        task.setSessionKey("sess_1");

        TaskEvent e = TaskExecutor.buildEvent(
                task,
                "trc_task_1",
                "run_1",
                EventType.TOOL_START,
                Map.of("tool", "command.exec"),
                7
        );

        assertNotNull(e.getEventId());
        assertEquals(1, e.getEventVersion());
        assertEquals(EventType.TOOL_START, e.getType());
        assertNotNull(e.getTimestamp());
        assertEquals("task_1", e.getTaskId());
        assertEquals("sess_id_1", e.getSessionId());
        assertEquals("codex", e.getAssistant());
        assertEquals(7, e.getSeq());
    }

    @Test
    void buildEventFallsBackToSessionKeyWhenSessionIdMissing() {
        TaskSummary task = new TaskSummary();
        task.setTaskId("task_2");
        task.setAssistant("codex");
        task.setSessionKey("legacy_session_key");

        TaskEvent e = TaskExecutor.buildEvent(
                task,
                "trc_task_2",
                "run_2",
                EventType.TOOL_START,
                Map.of("tool", "command.exec"),
                1
        );

        assertEquals("legacy_session_key", e.getSessionId());
    }
}

