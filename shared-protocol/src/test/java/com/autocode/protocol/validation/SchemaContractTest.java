package com.autocode.protocol.validation;

import com.autocode.protocol.model.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;

import java.time.Instant;
import java.util.Map;
import java.util.stream.Stream;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;

/**
 * Contract tests: validate Java DTOs against shared JSON Schema files.
 *
 * <p>Ensures that the Java model classes produce JSON that conforms to the
 * schema definitions in {@code shared-protocol/src/main/resources/schema/}.</p>
 */
class SchemaContractTest {
    private static final ObjectMapper MAPPER = new ObjectMapper();
    private static SchemaValidator validator;

    @BeforeAll
    static void setUp() {
        validator = new SchemaValidator();
    }

    // ------------------------------------------------------------------
    // EventAckResponse vs event_ack.v1.schema.json
    // ------------------------------------------------------------------

    static Stream<EventAckResponse> validAckResponses() {
        return Stream.of(
                EventAckResponse.accepted(1),
                EventAckResponse.accepted(0),
                EventAckResponse.duplicate(5),
                EventAckResponse.rejected(AckErrorCode.INVALID_NODE_ID),
                EventAckResponse.rejected(AckErrorCode.TASK_NOT_FOUND, 3),
                new EventAckResponse(0, false, false, null)
        );
    }

    @ParameterizedTest
    @MethodSource("validAckResponses")
    @DisplayName("EventAckResponse conforms to event_ack.v1.schema.json")
    void eventAckResponse_conformsToSchema(EventAckResponse ack) {
        assertDoesNotThrow(() ->
                validator.validate("schema/events/v1/event_ack.v1.schema.json", ack));
    }

    @Test
    @DisplayName("EventAckResponse accepted has required fields")
    void eventAckResponse_accepted_hasRequiredFields() {
        EventAckResponse ack = EventAckResponse.accepted(42);
        assertDoesNotThrow(() ->
                validator.validate("schema/events/v1/event_ack.v1.schema.json", ack));
    }

    @Test
    @DisplayName("EventAckResponse rejected carries errorCode")
    void eventAckResponse_rejected_carriesErrorCode() {
        EventAckResponse ack = EventAckResponse.rejected(AckErrorCode.PROCESSING_ERROR);
        assertDoesNotThrow(() ->
                validator.validate("schema/events/v1/event_ack.v1.schema.json", ack));
    }

    // ------------------------------------------------------------------
    // TaskEvent vs task_event.v1.schema.json
    // ------------------------------------------------------------------

    private TaskEvent createTaskEvent(EventType type) {
        TaskEvent event = new TaskEvent();
        event.setEventId("evt-" + System.nanoTime());
        event.setTaskId("task-001");
        event.setType(type);
        event.setTimestamp(Instant.now());
        event.setSeq(0);
        event.setEventVersion(1);
        return event;
    }

    static Stream<EventType> taskEventTypes() {
        return Stream.of(
                EventType.TASK_CREATED,
                EventType.TASK_STARTED,
                EventType.ASSISTANT_OUTPUT,
                EventType.TOOL_START,
                EventType.TOOL_END,
                EventType.BUILD_STARTED,
                EventType.BUILD_DONE,
                EventType.TASK_DONE,
                EventType.TASK_FAILED,
                EventType.HEARTBEAT
        );
    }

    @ParameterizedTest
    @MethodSource("taskEventTypes")
    @DisplayName("TaskEvent conforms to task_event.v1.schema.json")
    void taskEvent_conformsToSchema(EventType type) {
        TaskEvent event = createTaskEvent(type);
        assertDoesNotThrow(() ->
                validator.validate("schema/events/v1/task_event.v1.schema.json", event));
    }

    @Test
    @DisplayName("TaskEvent with optional fields conforms to schema")
    void taskEvent_withOptionalFields_conformsToSchema() {
        TaskEvent event = createTaskEvent(EventType.TASK_STARTED);
        event.setSessionId("sess-123");
        event.setAssistant("coder-agent");
        event.setPayload(Map.of("key", "value"));
        assertDoesNotThrow(() ->
                validator.validate("schema/events/v1/task_event.v1.schema.json", event));
    }

    // ------------------------------------------------------------------
    // SandboxHealthResponse vs sandbox_health_response.v1.schema.json
    // ------------------------------------------------------------------

    @Test
    @DisplayName("SandboxHealthResponse up() conforms to schema")
    void sandboxHealthResponse_up_conformsToSchema() {
        SandboxHealthResponse response = SandboxHealthResponse.up();
        assertDoesNotThrow(() ->
                validator.validate("schema/sandbox/v1/sandbox_health_response.v1.schema.json", response));
    }

    @Test
    @DisplayName("SandboxHealthResponse custom status conforms to schema")
    void sandboxHealthResponse_customStatus_conformsToSchema() {
        SandboxHealthResponse response = new SandboxHealthResponse();
        response.setOk(true);
        response.setStatus("healthy");
        assertDoesNotThrow(() ->
                validator.validate("schema/sandbox/v1/sandbox_health_response.v1.schema.json", response));
    }

    // ------------------------------------------------------------------
    // SandboxExecuteRequest vs sandbox_execute_request.v1.schema.json
    // ------------------------------------------------------------------

    @Test
    @DisplayName("SandboxExecuteRequest minimal conforms to schema")
    void sandboxExecuteRequest_minimal_conformsToSchema() {
        SandboxExecuteRequest request = new SandboxExecuteRequest();
        request.setTaskId("task-001");
        request.setCommand("echo hello");
        assertDoesNotThrow(() ->
                validator.validate("schema/sandbox/v1/sandbox_execute_request.v1.schema.json", request));
    }

    @Test
    @DisplayName("SandboxExecuteRequest full fields conforms to schema")
    void sandboxExecuteRequest_full_conformsToSchema() {
        SandboxExecuteRequest request = new SandboxExecuteRequest();
        request.setTaskId("task-001");
        request.setCommand("npm test");
        request.setCwd("/workspace");
        request.setPrompt("run tests");
        request.setTool("command.exec");
        request.setAction("run_command");
        request.setToolVersion("1.0");
        request.setTraceId("trace-abc");
        request.setRunId("run-123");
        request.setAssistant("coder-agent");
        request.setSessionId("sess-1");
        request.setSessionKey("key-1");
        request.setApprovalTimeoutSeconds(60L);
        assertDoesNotThrow(() ->
                validator.validate("schema/sandbox/v1/sandbox_execute_request.v1.schema.json", request));
    }

    // ------------------------------------------------------------------
    // SandboxExecuteResponse vs sandbox_execute_response.v1.schema.json
    // ------------------------------------------------------------------

    @Test
    @DisplayName("SandboxExecuteResponse success conforms to schema")
    void sandboxExecuteResponse_success_conformsToSchema() {
        SandboxExecuteResponse response = SandboxExecuteResponse.success(
                "completed", 0, "all tests passed", false,
                "command.exec", "1.0", "trace-abc", "run-123");
        assertDoesNotThrow(() ->
                validator.validate("schema/sandbox/v1/sandbox_execute_response.v1.schema.json", response));
    }

    @Test
    @DisplayName("SandboxExecuteResponse failure conforms to schema")
    void sandboxExecuteResponse_failure_conformsToSchema() {
        SandboxExecuteResponse response = SandboxExecuteResponse.failure(
                "failed", "command not found", true,
                "command.exec", "1.0", "trace-abc", "run-123", null);
        assertDoesNotThrow(() ->
                validator.validate("schema/sandbox/v1/sandbox_execute_response.v1.schema.json", response));
    }

    @Test
    @DisplayName("SandboxExecuteResponse with approvalId conforms to schema")
    void sandboxExecuteResponse_withApproval_conformsToSchema() {
        SandboxExecuteResponse response = SandboxExecuteResponse.failure(
                "approval_required", "needs approval", false,
                "command.exec", "1.0", "trace-abc", "run-123", "appr-456");
        assertDoesNotThrow(() ->
                validator.validate("schema/sandbox/v1/sandbox_execute_response.v1.schema.json", response));
    }
}
