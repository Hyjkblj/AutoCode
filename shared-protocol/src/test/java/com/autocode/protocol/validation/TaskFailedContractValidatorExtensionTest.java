package com.autocode.protocol.validation;

import com.autocode.protocol.model.EventType;
import com.autocode.protocol.model.TaskEvent;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.io.InputStream;
import java.time.Instant;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;

class TaskFailedContractValidatorExtensionTest {
    private static final ObjectMapper MAPPER = new ObjectMapper().findAndRegisterModules();

    @Test
    void task_failed_example_resource_is_valid() throws Exception {
        try (InputStream in = TaskFailedContractValidatorExtensionTest.class.getResourceAsStream("/examples/task_failed.v1.example.json")) {
            assertNotNull(in, "Missing test resource: /examples/task_failed.v1.example.json");
            TaskEvent event = MAPPER.readValue(in, TaskEvent.class);
            assertDoesNotThrow(() -> TaskEventContractValidator.validate(event));
        }
    }

    @Test
    void task_failed_requires_reason() {
        TaskEvent event = new TaskEvent();
        event.setEventId("e_tf_1");
        event.setTaskId("t_tf_1");
        event.setType(EventType.TASK_FAILED);
        event.setTimestamp(Instant.parse("2026-04-09T00:00:00Z"));
        event.setSeq(0);
        event.setEventVersion(1);
        event.setPayload(Map.of("detail", "no reason present"));

        assertThrows(ContractViolationException.class, () -> TaskEventContractValidator.validate(event));
    }

    @Test
    void task_failed_rejects_blank_error_code_when_present() {
        TaskEvent event = new TaskEvent();
        event.setEventId("e_tf_2");
        event.setTaskId("t_tf_2");
        event.setType(EventType.TASK_FAILED);
        event.setTimestamp(Instant.parse("2026-04-09T00:00:00Z"));
        event.setSeq(0);
        event.setEventVersion(1);
        event.setPayload(Map.of(
                "reason", "unsupported_target",
                "errorCode", "   "
        ));

        assertThrows(ContractViolationException.class, () -> TaskEventContractValidator.validate(event));
    }
}

