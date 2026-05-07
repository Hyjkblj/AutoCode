package com.autocode.protocol.validation;

import com.autocode.protocol.model.AckErrorCode;
import com.autocode.protocol.model.EventAckResponse;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;

import java.util.stream.Stream;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertThrows;

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
}
