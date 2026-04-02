package com.autocode.protocol.validation;

import com.autocode.protocol.model.ServiceRuntimeDescriptor;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.io.InputStream;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;

class ServiceRuntimeDescriptorContractValidatorTest {
    private static final ObjectMapper MAPPER = new ObjectMapper().findAndRegisterModules();

    @Test
    void example_resource_is_valid() throws Exception {
        try (InputStream in = ServiceRuntimeDescriptorContractValidatorTest.class.getResourceAsStream("/examples/service_runtime_descriptor.v1.example.json")) {
            assertNotNull(in, "Missing test resource: /examples/service_runtime_descriptor.v1.example.json");
            ServiceRuntimeDescriptor d = MAPPER.readValue(in, ServiceRuntimeDescriptor.class);
            assertDoesNotThrow(() -> ServiceRuntimeDescriptorContractValidator.validate(d));
        }
    }

    @Test
    void invalid_port_rejected() {
        ServiceRuntimeDescriptor d = new ServiceRuntimeDescriptor();
        d.setSchemaVersion(1);
        d.setServiceId("s1");
        var p = new ServiceRuntimeDescriptor.PortBinding();
        p.setPort(0);
        d.setPorts(List.of(p));
        assertThrows(ContractViolationException.class, () -> ServiceRuntimeDescriptorContractValidator.validate(d));
    }
}
