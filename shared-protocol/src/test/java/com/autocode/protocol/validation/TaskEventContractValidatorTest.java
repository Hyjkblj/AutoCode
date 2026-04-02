package com.autocode.protocol.validation;

import com.autocode.protocol.model.EventType;
import com.autocode.protocol.model.TaskEvent;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.io.InputStream;
import java.time.Instant;
import java.util.HashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;

class TaskEventContractValidatorTest {
    private static final ObjectMapper MAPPER = new ObjectMapper().findAndRegisterModules();

    @Test
    void artifactReady_example_resource_is_valid() throws Exception {
        try (InputStream in = TaskEventContractValidatorTest.class.getResourceAsStream("/examples/artifact_ready.v1.example.json")) {
            assertNotNull(in, "Missing test resource: /examples/artifact_ready.v1.example.json");
            TaskEvent event = MAPPER.readValue(in, TaskEvent.class);
            assertDoesNotThrow(() -> TaskEventContractValidator.validate(event));
        }
    }

    @Test
    void artifactReady_requires_artifactId_and_type() {
        TaskEvent event = new TaskEvent();
        event.setEventId("e1");
        event.setTaskId("t1");
        event.setType(EventType.ARTIFACT_READY);
        event.setTimestamp(Instant.parse("2026-04-01T00:00:00Z"));
        event.setSeq(0);
        event.setEventVersion(1);
        event.setPayload(Map.of("artifact", Map.of("artifactId", "a1")));

        assertThrows(ContractViolationException.class, () -> TaskEventContractValidator.validate(event));
    }

    @Test
    void specProposed_example_resource_is_valid() throws Exception {
        try (InputStream in = TaskEventContractValidatorTest.class.getResourceAsStream("/examples/spec_proposed.v1.example.json")) {
            assertNotNull(in, "Missing test resource: /examples/spec_proposed.v1.example.json");
            TaskEvent event = MAPPER.readValue(in, TaskEvent.class);
            assertDoesNotThrow(() -> TaskEventContractValidator.validate(event));
        }
    }

    @Test
    void unsupported_event_version_rejected() {
        TaskEvent event = new TaskEvent();
        event.setEventId("e1");
        event.setTaskId("t1");
        event.setType(EventType.ARTIFACT_READY);
        event.setTimestamp(Instant.parse("2026-04-01T00:00:00Z"));
        event.setSeq(0);
        event.setEventVersion(2);
        event.setPayload(Map.of("artifact", Map.of("artifactId", "a1", "type", "zip")));

        assertThrows(ContractViolationException.class, () -> TaskEventContractValidator.validate(event));
    }

    @Test
    void artifact_ready_rejects_build_without_command() {
        TaskEvent event = new TaskEvent();
        event.setEventId("e1");
        event.setTaskId("t1");
        event.setType(EventType.ARTIFACT_READY);
        event.setTimestamp(Instant.parse("2026-04-01T00:00:00Z"));
        event.setSeq(0);
        event.setEventVersion(1);
        Map<String, Object> artifact = new HashMap<>();
        artifact.put("artifactId", "a1");
        artifact.put("type", "zip");
        artifact.put("build", Map.of());
        event.setPayload(Map.of("artifact", artifact));

        assertThrows(ContractViolationException.class, () -> TaskEventContractValidator.validate(event));
    }
}
