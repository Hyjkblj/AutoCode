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
        assertEquals("sess_1", e.getSessionId());
        assertEquals("codex", e.getAssistant());
        assertEquals(7, e.getSeq());
    }
}

