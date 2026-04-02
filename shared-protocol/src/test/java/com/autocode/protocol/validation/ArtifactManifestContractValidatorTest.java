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

    @Test
    void unsupported_schema_version() {
        ArtifactManifest m = new ArtifactManifest();
        m.setSchemaVersion(2);
        ArtifactMetadata a = new ArtifactMetadata();
        a.setArtifactId("a1");
        a.setType("zip");
        m.setArtifacts(List.of(a));
        assertThrows(ContractViolationException.class, () -> ArtifactManifestContractValidator.validate(m));
    }

    @Test
    void empty_artifacts_rejected() {
        ArtifactManifest m = new ArtifactManifest();
        m.setSchemaVersion(1);
        m.setArtifacts(List.of());
        assertThrows(ContractViolationException.class, () -> ArtifactManifestContractValidator.validate(m));
    }

    @Test
    void duplicate_artifact_ids_in_manifest_rejected() {
        ArtifactManifest m = new ArtifactManifest();
        m.setSchemaVersion(1);
        ArtifactMetadata a1 = new ArtifactMetadata();
        a1.setArtifactId("dup");
        a1.setType("zip");
        ArtifactMetadata a2 = new ArtifactMetadata();
        a2.setArtifactId("dup");
        a2.setType("spec_bundle");
        m.setArtifacts(List.of(a1, a2));
        assertThrows(ContractViolationException.class, () -> ArtifactManifestContractValidator.validate(m));
    }
}
