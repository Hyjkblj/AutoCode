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
    void specProposed_requires_artifact() {
        TaskEvent event = new TaskEvent();
        event.setEventId("e9");
        event.setTaskId("t9");
        event.setType(EventType.SPEC_PROPOSED);
        event.setTimestamp(Instant.parse("2026-04-06T00:00:00Z"));
        event.setSeq(0);
        event.setEventVersion(1);
        event.setPayload(Map.of("path", "spec.json"));

        assertThrows(ContractViolationException.class, () -> TaskEventContractValidator.validate(event));
    }

    @Test
    void filePatchPreview_example_resource_is_valid() throws Exception {
        try (InputStream in = TaskEventContractValidatorTest.class.getResourceAsStream("/examples/file_patch_preview.v1.example.json")) {
            assertNotNull(in, "Missing test resource: /examples/file_patch_preview.v1.example.json");
            TaskEvent event = MAPPER.readValue(in, TaskEvent.class);
            assertDoesNotThrow(() -> TaskEventContractValidator.validate(event));
        }
    }

    @Test
    void approvalRequired_example_resource_is_valid() throws Exception {
        try (InputStream in = TaskEventContractValidatorTest.class.getResourceAsStream("/examples/approval_required.v1.example.json")) {
            assertNotNull(in, "Missing test resource: /examples/approval_required.v1.example.json");
            TaskEvent event = MAPPER.readValue(in, TaskEvent.class);
            assertDoesNotThrow(() -> TaskEventContractValidator.validate(event));
        }
    }

    @Test
    void approvalResult_example_resource_is_valid() throws Exception {
        try (InputStream in = TaskEventContractValidatorTest.class.getResourceAsStream("/examples/approval_result.v1.example.json")) {
            assertNotNull(in, "Missing test resource: /examples/approval_result.v1.example.json");
            TaskEvent event = MAPPER.readValue(in, TaskEvent.class);
            assertDoesNotThrow(() -> TaskEventContractValidator.validate(event));
        }
    }

    @Test
    void toolStart_example_resource_is_valid() throws Exception {
        try (InputStream in = TaskEventContractValidatorTest.class.getResourceAsStream("/examples/tool_start.v1.example.json")) {
            assertNotNull(in, "Missing test resource: /examples/tool_start.v1.example.json");
            TaskEvent event = MAPPER.readValue(in, TaskEvent.class);
            assertDoesNotThrow(() -> TaskEventContractValidator.validate(event));
        }
    }

    @Test
    void toolEnd_example_resource_is_valid() throws Exception {
        try (InputStream in = TaskEventContractValidatorTest.class.getResourceAsStream("/examples/tool_end.v1.example.json")) {
            assertNotNull(in, "Missing test resource: /examples/tool_end.v1.example.json");
            TaskEvent event = MAPPER.readValue(in, TaskEvent.class);
            assertDoesNotThrow(() -> TaskEventContractValidator.validate(event));
        }
    }

    @Test
    void buildStarted_example_resource_is_valid() throws Exception {
        try (InputStream in = TaskEventContractValidatorTest.class.getResourceAsStream("/examples/build_started.v1.example.json")) {
            assertNotNull(in, "Missing test resource: /examples/build_started.v1.example.json");
            TaskEvent event = MAPPER.readValue(in, TaskEvent.class);
            assertDoesNotThrow(() -> TaskEventContractValidator.validate(event));
        }
    }

    @Test
    void buildLog_example_resource_is_valid() throws Exception {
        try (InputStream in = TaskEventContractValidatorTest.class.getResourceAsStream("/examples/build_log.v1.example.json")) {
            assertNotNull(in, "Missing test resource: /examples/build_log.v1.example.json");
            TaskEvent event = MAPPER.readValue(in, TaskEvent.class);
            assertDoesNotThrow(() -> TaskEventContractValidator.validate(event));
        }
    }

    @Test
    void buildDone_example_resource_is_valid() throws Exception {
        try (InputStream in = TaskEventContractValidatorTest.class.getResourceAsStream("/examples/build_done.v1.example.json")) {
            assertNotNull(in, "Missing test resource: /examples/build_done.v1.example.json");
            TaskEvent event = MAPPER.readValue(in, TaskEvent.class);
            assertDoesNotThrow(() -> TaskEventContractValidator.validate(event));
        }
    }

    @Test
    void deployPlan_example_resource_is_valid() throws Exception {
        try (InputStream in = TaskEventContractValidatorTest.class.getResourceAsStream("/examples/deploy_plan.v1.example.json")) {
            assertNotNull(in, "Missing test resource: /examples/deploy_plan.v1.example.json");
            TaskEvent event = MAPPER.readValue(in, TaskEvent.class);
            assertDoesNotThrow(() -> TaskEventContractValidator.validate(event));
        }
    }

    @Test
    void deployResult_example_resource_is_valid() throws Exception {
        try (InputStream in = TaskEventContractValidatorTest.class.getResourceAsStream("/examples/deploy_result.v1.example.json")) {
            assertNotNull(in, "Missing test resource: /examples/deploy_result.v1.example.json");
            TaskEvent event = MAPPER.readValue(in, TaskEvent.class);
            assertDoesNotThrow(() -> TaskEventContractValidator.validate(event));
        }
    }

    @Test
    void taskDone_example_resource_is_valid() throws Exception {
        try (InputStream in = TaskEventContractValidatorTest.class.getResourceAsStream("/examples/task_done.v1.example.json")) {
            assertNotNull(in, "Missing test resource: /examples/task_done.v1.example.json");
            TaskEvent event = MAPPER.readValue(in, TaskEvent.class);
            assertDoesNotThrow(() -> TaskEventContractValidator.validate(event));
        }
    }

    @Test
    void taskFailed_example_resource_is_valid() throws Exception {
        try (InputStream in = TaskEventContractValidatorTest.class.getResourceAsStream("/examples/task_failed.v1.example.json")) {
            assertNotNull(in, "Missing test resource: /examples/task_failed.v1.example.json");
            TaskEvent event = MAPPER.readValue(in, TaskEvent.class);
            assertDoesNotThrow(() -> TaskEventContractValidator.validate(event));
        }
    }

    @Test
    void taskCreated_example_resource_is_valid() throws Exception {
        try (InputStream in = TaskEventContractValidatorTest.class.getResourceAsStream("/examples/task_created.v1.example.json")) {
            assertNotNull(in, "Missing test resource: /examples/task_created.v1.example.json");
            TaskEvent event = MAPPER.readValue(in, TaskEvent.class);
            assertDoesNotThrow(() -> TaskEventContractValidator.validate(event));
        }
    }

    @Test
    void taskStarted_example_resource_is_valid() throws Exception {
        try (InputStream in = TaskEventContractValidatorTest.class.getResourceAsStream("/examples/task_started.v1.example.json")) {
            assertNotNull(in, "Missing test resource: /examples/task_started.v1.example.json");
            TaskEvent event = MAPPER.readValue(in, TaskEvent.class);
            assertDoesNotThrow(() -> TaskEventContractValidator.validate(event));
        }
    }

    @Test
    void assistantOutput_example_resource_is_valid() throws Exception {
        try (InputStream in = TaskEventContractValidatorTest.class.getResourceAsStream("/examples/assistant_output.v1.example.json")) {
            assertNotNull(in, "Missing test resource: /examples/assistant_output.v1.example.json");
            TaskEvent event = MAPPER.readValue(in, TaskEvent.class);
            assertDoesNotThrow(() -> TaskEventContractValidator.validate(event));
        }
    }

    @Test
    void heartbeat_example_resource_is_valid() throws Exception {
        try (InputStream in = TaskEventContractValidatorTest.class.getResourceAsStream("/examples/heartbeat.v1.example.json")) {
            assertNotNull(in, "Missing test resource: /examples/heartbeat.v1.example.json");
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

    @Test
    void deploy_plan_requires_requestId() {
        TaskEvent event = new TaskEvent();
        event.setEventId("e2");
        event.setTaskId("t2");
        event.setType(EventType.DEPLOY_PLAN);
        event.setTimestamp(Instant.parse("2026-04-04T00:00:00Z"));
        event.setSeq(0);
        event.setEventVersion(1);
        event.setPayload(Map.of(
                "environment", "staging",
                "artifact", Map.of("artifactId", "a1", "type", "zip")
        ));

        assertThrows(ContractViolationException.class, () -> TaskEventContractValidator.validate(event));
    }

    @Test
    void deploy_result_requires_status() {
        TaskEvent event = new TaskEvent();
        event.setEventId("e3");
        event.setTaskId("t3");
        event.setType(EventType.DEPLOY_RESULT);
        event.setTimestamp(Instant.parse("2026-04-04T00:00:00Z"));
        event.setSeq(0);
        event.setEventVersion(1);
        event.setPayload(Map.of("requestId", "deploy_req_001"));

        assertThrows(ContractViolationException.class, () -> TaskEventContractValidator.validate(event));
    }

    @Test
    void approval_required_requires_context() {
        TaskEvent event = new TaskEvent();
        event.setEventId("e4");
        event.setTaskId("t4");
        event.setType(EventType.APPROVAL_REQUIRED);
        event.setTimestamp(Instant.parse("2026-04-04T00:00:00Z"));
        event.setSeq(0);
        event.setEventVersion(1);
        event.setPayload(Map.of("approvalId", "apr_001"));

        assertThrows(ContractViolationException.class, () -> TaskEventContractValidator.validate(event));
    }

    @Test
    void tool_start_requires_tool() {
        TaskEvent event = new TaskEvent();
        event.setEventId("e5");
        event.setTaskId("t5");
        event.setType(EventType.TOOL_START);
        event.setTimestamp(Instant.parse("2026-04-05T00:00:00Z"));
        event.setSeq(0);
        event.setEventVersion(1);
        event.setPayload(Map.of("action", "run_command"));

        assertThrows(ContractViolationException.class, () -> TaskEventContractValidator.validate(event));
    }

    @Test
    void tool_end_requires_status() {
        TaskEvent event = new TaskEvent();
        event.setEventId("e6");
        event.setTaskId("t6");
        event.setType(EventType.TOOL_END);
        event.setTimestamp(Instant.parse("2026-04-05T00:00:00Z"));
        event.setSeq(0);
        event.setEventVersion(1);
        event.setPayload(Map.of("tool", "command.exec"));

        assertThrows(ContractViolationException.class, () -> TaskEventContractValidator.validate(event));
    }

    @Test
    void build_log_requires_message() {
        TaskEvent event = new TaskEvent();
        event.setEventId("e7");
        event.setTaskId("t7");
        event.setType(EventType.BUILD_LOG);
        event.setTimestamp(Instant.parse("2026-04-04T00:00:00Z"));
        event.setSeq(0);
        event.setEventVersion(1);
        event.setPayload(Map.of("buildId", "build_001", "level", "info"));

        assertThrows(ContractViolationException.class, () -> TaskEventContractValidator.validate(event));
    }

    @Test
    void file_patch_preview_requires_patch_or_files() {
        TaskEvent event = new TaskEvent();
        event.setEventId("e8");
        event.setTaskId("t8");
        event.setType(EventType.FILE_PATCH_PREVIEW);
        event.setTimestamp(Instant.parse("2026-04-04T00:00:00Z"));
        event.setSeq(0);
        event.setEventVersion(1);
        event.setPayload(Map.of("format", "unified"));

        assertThrows(ContractViolationException.class, () -> TaskEventContractValidator.validate(event));
    }

    @Test
    void task_done_requires_result() {
        TaskEvent event = new TaskEvent();
        event.setEventId("e10");
        event.setTaskId("t10");
        event.setType(EventType.TASK_DONE);
        event.setTimestamp(Instant.parse("2026-04-08T00:00:00Z"));
        event.setSeq(0);
        event.setEventVersion(1);
        event.setPayload(Map.of("status", "ok"));

        assertThrows(ContractViolationException.class, () -> TaskEventContractValidator.validate(event));
    }

    @Test
    void task_failed_requires_reason() {
        TaskEvent event = new TaskEvent();
        event.setEventId("e11");
        event.setTaskId("t11");
        event.setType(EventType.TASK_FAILED);
        event.setTimestamp(Instant.parse("2026-04-08T00:00:00Z"));
        event.setSeq(0);
        event.setEventVersion(1);
        event.setPayload(Map.of("status", "error"));

        assertThrows(ContractViolationException.class, () -> TaskEventContractValidator.validate(event));
    }

    @Test
    void task_created_requires_projectId() {
        TaskEvent event = new TaskEvent();
        event.setEventId("e12");
        event.setTaskId("t12");
        event.setType(EventType.TASK_CREATED);
        event.setTimestamp(Instant.parse("2026-04-08T00:00:00Z"));
        event.setSeq(0);
        event.setEventVersion(1);
        event.setPayload(Map.of("assistant", "gpt"));

        assertThrows(ContractViolationException.class, () -> TaskEventContractValidator.validate(event));
    }

    @Test
    void task_started_requires_nodeId() {
        TaskEvent event = new TaskEvent();
        event.setEventId("e13");
        event.setTaskId("t13");
        event.setType(EventType.TASK_STARTED);
        event.setTimestamp(Instant.parse("2026-04-08T00:00:00Z"));
        event.setSeq(0);
        event.setEventVersion(1);
        event.setPayload(Map.of("stage", "lease_acquired"));

        assertThrows(ContractViolationException.class, () -> TaskEventContractValidator.validate(event));
    }

    @Test
    void assistant_output_requires_message() {
        TaskEvent event = new TaskEvent();
        event.setEventId("e14");
        event.setTaskId("t14");
        event.setType(EventType.ASSISTANT_OUTPUT);
        event.setTimestamp(Instant.parse("2026-04-08T00:00:00Z"));
        event.setSeq(0);
        event.setEventVersion(1);
        event.setPayload(Map.of("stage", "PlannerAgent"));

        assertThrows(ContractViolationException.class, () -> TaskEventContractValidator.validate(event));
    }
}
