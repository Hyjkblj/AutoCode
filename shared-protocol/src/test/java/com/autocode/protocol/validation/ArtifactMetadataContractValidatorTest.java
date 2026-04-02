package com.autocode.protocol.validation;

import com.autocode.protocol.model.ArtifactMetadata;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertThrows;

class ArtifactMetadataContractValidatorTest {

    @Test
    void build_present_requires_command_on_dto() {
        ArtifactMetadata a = new ArtifactMetadata();
        a.setBuild(new ArtifactMetadata.BuildDescriptor());
        assertThrows(ContractViolationException.class, () -> ArtifactMetadataContractValidator.validateNestedDescriptors(a));
    }

    @Test
    void build_with_command_ok() {
        ArtifactMetadata a = new ArtifactMetadata();
        ArtifactMetadata.BuildDescriptor b = new ArtifactMetadata.BuildDescriptor();
        b.setCommand("mvn -q test");
        a.setBuild(b);
        assertDoesNotThrow(() -> ArtifactMetadataContractValidator.validateNestedDescriptors(a));
    }

    @Test
    void map_build_empty_object_rejected() {
        Map<String, Object> artifact = Map.of("build", Map.of());
        assertThrows(ContractViolationException.class, () -> ArtifactMetadataContractValidator.validateNestedDescriptorsFromMap(artifact));
    }

    @Test
    void duplicate_artifact_ids_rejected() {
        ArtifactMetadata a1 = new ArtifactMetadata();
        a1.setArtifactId("x");
        a1.setType("zip");
        ArtifactMetadata a2 = new ArtifactMetadata();
        a2.setArtifactId("x");
        a2.setType("zip");
        assertThrows(ContractViolationException.class, () -> ArtifactMetadataContractValidator.assertUniqueArtifactIds(List.of(a1, a2)));
    }
}
