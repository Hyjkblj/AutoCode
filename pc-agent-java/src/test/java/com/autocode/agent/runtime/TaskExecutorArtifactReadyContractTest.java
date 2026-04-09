package com.autocode.agent.runtime;

import com.autocode.protocol.model.EventType;
import com.autocode.protocol.model.TaskEvent;
import com.autocode.protocol.model.TaskSummary;
import com.autocode.protocol.validation.TaskEventContractValidator;
import org.junit.jupiter.api.Test;

import java.util.HashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class TaskExecutorArtifactReadyContractTest {

    @Test
    void artifactReadyPayloadOmitsTraceCorrelationForSchema() {
        Map<String, Object> artifact = new HashMap<>();
        artifact.put("artifactId", "art_1");
        artifact.put("type", "zip");
        artifact.put("hash", "sha256:aa");
        artifact.put("size", 42L);
        Map<String, Object> ready = new HashMap<>();
        ready.put("artifact", artifact);
        ready.put("kind", "zip");

        Map<String, Object> merged = TaskExecutor.mergeOutboundPayload(
                EventType.ARTIFACT_READY, "trc_1", "run_1", ready);
        assertFalse(merged.containsKey("traceId"));
        assertFalse(merged.containsKey("runId"));
        assertEquals("zip", merged.get("kind"));

        TaskSummary task = new TaskSummary();
        task.setTaskId("task_1");
        task.setAssistant("codex");
        task.setSessionId("sess_id_1");
        task.setSessionKey("sess_1");
        TaskEvent e = TaskExecutor.buildEvent(task, "trc_1", "run_1", EventType.ARTIFACT_READY, merged, 3);
        e.setPayload(merged);
        TaskEventContractValidator.validate(e);
        assertEquals("sess_id_1", e.getSessionId());
    }

    @Test
    void otherEventsStillMergeCorrelationIds() {
        Map<String, Object> merged = TaskExecutor.mergeOutboundPayload(
                EventType.TOOL_START, "trc_x", "run_y", Map.of("tool", "command.exec"));
        assertTrue(merged.containsKey("traceId"));
        assertTrue(merged.containsKey("runId"));
        assertEquals("command.exec", merged.get("tool"));
    }
}
