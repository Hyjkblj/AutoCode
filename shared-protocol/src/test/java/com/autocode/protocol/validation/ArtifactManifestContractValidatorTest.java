package com.autocode.protocol.validation;

import com.autocode.protocol.model.ArtifactManifest;
import com.autocode.protocol.model.ArtifactMetadata;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.io.InputStream;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;

class ArtifactManifestContractValidatorTest {
    private static final ObjectMapper MAPPER = new ObjectMapper().findAndRegisterModules();

    @Test
    void manifest_example_resource_is_valid() throws Exception {
        try (InputStream in = ArtifactManifestContractValidatorTest.class.getResourceAsStream("/examples/artifact_manifest.v1.example.json")) {
            assertNotNull(in, "Missing test resource: /examples/artifact_manifest.v1.example.json");
            ArtifactManifest manifest = MAPPER.readValue(in, ArtifactManifest.class);
            assertDoesNotThrow(() -> ArtifactManifestContractValidator.validate(manifest));
        }
    }

    @Test
    void defaultArtifactId_must_exist_in_list() {
        ArtifactManifest m = new ArtifactManifest();
        m.setSchemaVersion(1);
        ArtifactMetadata a = new ArtifactMetadata();
        a.setArtifactId("a1");
        a.setType("zip");
        m.setArtifacts(List.of(a));
        m.setDefaultArtifactId("missing");

        assertThrows(ContractViolationException.class, () -> ArtifactManifestContractValidator.validate(m));
    }
}
