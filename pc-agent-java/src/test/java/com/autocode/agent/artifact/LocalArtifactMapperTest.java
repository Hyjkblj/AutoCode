package com.autocode.agent.artifact;

import com.autocode.protocol.model.ArtifactMetadata;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class LocalArtifactMapperTest {

    @Test
    void guessMimeForZip() {
        assertEquals("application/zip", LocalArtifactMapper.guessMimeType("dist.zip"));
    }

    @Test
    void inferTypeForZip() {
        assertEquals("zip", LocalArtifactMapper.inferArtifactType("build.zip"));
    }

    @Test
    void inferKindPrefersMetadataType() {
        ArtifactMetadata m = new ArtifactMetadata();
        m.setType("patch");
        assertEquals("patch", LocalArtifactMapper.inferKind(m));
    }

    @Test
    void applyServerMetadataDefaultsFillsTypeAndMime() {
        ArtifactMetadata m = new ArtifactMetadata();
        m.setArtifactId("x");
        LocalArtifactMapper.applyServerMetadataDefaults(m, "out.zip");
        assertEquals("zip", m.getType());
        assertEquals("application/zip", m.getMime());
    }
}
