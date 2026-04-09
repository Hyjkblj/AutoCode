package com.autocode.protocol.validation;

import com.autocode.protocol.model.TaskEvent;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.io.InputStream;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertNotNull;

class Nl2WebEventContractValidatorExtensionTest {
    private static final ObjectMapper MAPPER = new ObjectMapper().findAndRegisterModules();

    @Test
    void artifact_ready_nl2web_example_resource_is_valid() throws Exception {
        try (InputStream in = Nl2WebEventContractValidatorExtensionTest.class.getResourceAsStream("/examples/artifact_ready_nl2web.v1.example.json")) {
            assertNotNull(in, "Missing test resource: /examples/artifact_ready_nl2web.v1.example.json");
            TaskEvent event = MAPPER.readValue(in, TaskEvent.class);
            assertDoesNotThrow(() -> TaskEventContractValidator.validate(event));
        }
    }
}

