package com.autocode.agent.client;

import com.autocode.protocol.model.ArtifactMetadata;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.assertThrows;

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

    @Test
    void fromMetadataIncludesOptionalDescriptorFields() {
        ArtifactMetadata meta = new ArtifactMetadata();
        meta.setArtifactId("art_runtime_1");
        meta.setType("runtime");
        meta.setName("service_runtime_descriptor.v1.json");
        meta.setDownloadUrl("https://example.local/a/art_runtime_1");
        meta.setEntryPath("runtime/service_runtime_descriptor.v1.json");

        ArtifactMetadata.BuildDescriptor build = new ArtifactMetadata.BuildDescriptor();
        build.setCommand("mvn -pl control-plane-spring spring-boot:run");
        build.setWorkingDir("control-plane-spring");
        meta.setBuild(build);

        ArtifactMetadata.RunDescriptor run = new ArtifactMetadata.RunDescriptor();
        run.setCommand("mvn -pl control-plane-spring spring-boot:run");
        run.setHints(List.of("http://127.0.0.1:8080/actuator/health", "  ", "http://127.0.0.1:8080/actuator/health"));
        meta.setRun(run);

        Map<String, Object> payload = ArtifactReadyPayloads.fromMetadata(meta, "runtime");
        @SuppressWarnings("unchecked")
        Map<String, Object> artifact = (Map<String, Object>) payload.get("artifact");
        assertEquals("service_runtime_descriptor.v1.json", artifact.get("name"));
        assertEquals("https://example.local/a/art_runtime_1", artifact.get("downloadUrl"));
        assertEquals("runtime/service_runtime_descriptor.v1.json", artifact.get("entryPath"));

        @SuppressWarnings("unchecked")
        Map<String, Object> buildMap = (Map<String, Object>) artifact.get("build");
        assertEquals("mvn -pl control-plane-spring spring-boot:run", buildMap.get("command"));
        assertEquals("control-plane-spring", buildMap.get("workingDir"));

        @SuppressWarnings("unchecked")
        Map<String, Object> runMap = (Map<String, Object>) artifact.get("run");
        assertEquals("mvn -pl control-plane-spring spring-boot:run", runMap.get("command"));
        assertEquals(List.of("http://127.0.0.1:8080/actuator/health"), runMap.get("hints"));
    }

    @Test
    void fromMetadataRejectsBuildWithoutCommand() {
        ArtifactMetadata meta = new ArtifactMetadata();
        meta.setArtifactId("art_invalid");
        meta.setType("runtime");
        ArtifactMetadata.BuildDescriptor build = new ArtifactMetadata.BuildDescriptor();
        build.setCommand("  ");
        meta.setBuild(build);
        assertThrows(IllegalArgumentException.class, () -> ArtifactReadyPayloads.fromMetadata(meta));
    }
}

