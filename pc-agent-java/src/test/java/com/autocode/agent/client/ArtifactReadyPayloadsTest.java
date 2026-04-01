package com.autocode.agent.client;

import com.autocode.protocol.model.ArtifactMetadata;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ArtifactReadyPayloadsTest {

    @Test
    void fromMetadataBuildsArtifactReadyV1Shape() {
        ArtifactMetadata meta = new ArtifactMetadata();
        meta.setArtifactId("art_1");
        meta.setType("zip");
        meta.setHash("sha256:abc");
        meta.setSize(123L);
        meta.setMime("application/zip");

        Map<String, Object> payload = ArtifactReadyPayloads.fromMetadata(meta, "zip");

        Object artifact = payload.get("artifact");
        assertNotNull(artifact);
        assertTrue(artifact instanceof Map);
        @SuppressWarnings("unchecked")
        Map<String, Object> a = (Map<String, Object>) artifact;
        assertEquals("art_1", a.get("artifactId"));
        assertEquals("zip", a.get("type"));
        assertEquals("sha256:abc", a.get("hash"));
        assertEquals(123L, a.get("size"));
        assertEquals("application/zip", a.get("mime"));
        assertEquals("zip", payload.get("kind"));
    }

    @Test
    void fromMetadataOmitsOptionalFieldsWhenBlank() {
        ArtifactMetadata meta = new ArtifactMetadata();
        meta.setArtifactId("art_2");
        meta.setType("patch");
        meta.setHash("  ");
        meta.setMime(" ");

        Map<String, Object> payload = ArtifactReadyPayloads.fromMetadata(meta);
        @SuppressWarnings("unchecked")
        Map<String, Object> a = (Map<String, Object>) payload.get("artifact");
        assertEquals("art_2", a.get("artifactId"));
        assertEquals("patch", a.get("type"));
        assertNull(a.get("hash"));
        assertNull(a.get("mime"));
        assertNull(payload.get("kind"));
    }
}

