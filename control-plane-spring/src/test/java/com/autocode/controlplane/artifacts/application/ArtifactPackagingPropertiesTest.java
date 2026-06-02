package com.autocode.controlplane.artifacts.application;

import com.autocode.controlplane.artifacts.domain.ArtifactContent;
import com.autocode.controlplane.artifacts.domain.ArtifactRecord;
import com.autocode.controlplane.artifacts.ports.ArtifactsPort;
import com.autocode.controlplane.artifacts.ports.AuditPort;
import com.autocode.controlplane.artifacts.ports.DownloadAuthzPort;
import com.autocode.controlplane.artifacts.ports.TaskReadPort;
import com.autocode.controlplane.security.ProjectAuthz;
import net.jqwik.api.*;
import net.jqwik.api.constraints.AlphaChars;
import net.jqwik.api.constraints.NotBlank;
import net.jqwik.api.constraints.Size;
import net.jqwik.api.constraints.StringLength;
import org.mockito.Mockito;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.time.Instant;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

/**
 * Property-based tests for artifact packaging and hosting.
 *
 * <p><b>Property 13: Artifact Packaging and Hosting</b><br>
 * For any completed generation task, the Artifact_Service SHALL package the generated code
 * and make it accessible via HTTP.
 *
 * <p><b>Validates: Requirements 3.6</b>
 */
class ArtifactPackagingPropertiesTest {

    // -----------------------------------------------------------------------
    // Helpers
    // -----------------------------------------------------------------------

    private ArtifactsService buildService(ArtifactsPort port) {
        TaskReadPort taskReadPort = mock(TaskReadPort.class);
        when(taskReadPort.exists(anyString())).thenReturn(true);

        DownloadAuthzPort downloadAuthzPort = mock(DownloadAuthzPort.class);
        when(downloadAuthzPort.canDownload(anyString(), anyString(), any())).thenReturn(true);

        AuditPort auditPort = mock(AuditPort.class);
        ProjectAuthz projectAuthz = mock(ProjectAuthz.class);

        return new ArtifactsService(port, downloadAuthzPort, auditPort, taskReadPort, projectAuthz);
    }

    /**
     * In-memory ArtifactsPort that stores bytes in a map so tests can inspect them.
     */
    private static class InMemoryArtifactsPort implements ArtifactsPort {
        private final Map<String, byte[]> stored = new HashMap<>();
        private final Map<String, ArtifactRecord> records = new HashMap<>();
        private int storeCallCount = 0;

        @Override
        public ArtifactRecord store(String taskId, String name, String contentType, InputStream data) {
            storeCallCount++;
            String artifactId = "art_" + storeCallCount;
            byte[] bytes;
            try {
                bytes = data.readAllBytes();
            } catch (IOException e) {
                throw new IllegalStateException("failed to read artifact data", e);
            }
            stored.put(artifactId, bytes);
            ArtifactRecord record = new ArtifactRecord(
                    artifactId, taskId, name, contentType, bytes.length, "sha256_" + artifactId, Instant.now()
            );
            records.put(artifactId, record);
            return record;
        }

        @Override
        public List<ArtifactRecord> listByTask(String taskId) {
            return records.values().stream()
                    .filter(r -> taskId.equals(r.taskId()))
                    .toList();
        }

        @Override
        public ArtifactContent open(String taskId, String artifactId) {
            ArtifactRecord record = records.get(artifactId);
            if (record == null) {
                throw new ArtifactNotFoundException("artifact not found");
            }
            byte[] bytes = stored.get(artifactId);
            return new ArtifactContent(record, new ByteArrayInputStream(bytes));
        }

        byte[] getBytes(String artifactId) {
            return stored.get(artifactId);
        }
    }

    // -----------------------------------------------------------------------
    // Property 13 — Artifact Packaging and Hosting
    // -----------------------------------------------------------------------

    /**
     * For any completed generation task with a non-empty set of generated files,
     * packageAsZip SHALL produce a stored artifact with content-type application/zip
     * and a positive size.
     *
     * <b>Validates: Requirements 3.6</b>
     */
    @Property(tries = 100)
    @Label("packageAsZip always produces a stored artifact with application/zip content-type")
    void packageAsZip_alwaysProducesStoredZipArtifact(
            @ForAll @AlphaChars @StringLength(min = 3, max = 20) String taskIdSuffix,
            @ForAll @AlphaChars @StringLength(min = 1, max = 10) String fileName,
            @ForAll @Size(min = 1, max = 5) List<@AlphaChars @StringLength(min = 1, max = 8) String> fileNames
    ) {
        String taskId = "tsk_" + taskIdSuffix;
        InMemoryArtifactsPort port = new InMemoryArtifactsPort();
        ArtifactsService service = buildService(port);

        Map<String, byte[]> files = new HashMap<>();
        for (String name : fileNames) {
            files.put(name + ".py", ("# " + name).getBytes());
        }

        ArtifactRecord record = service.packageAsZip(taskId, fileName + ".zip", files, Map.of("intent", "backend"));

        assertThat(record).isNotNull();
        assertThat(record.artifactId()).isNotBlank();
        assertThat(record.taskId()).isEqualTo(taskId);
        assertThat(record.contentType()).isEqualTo("application/zip");
        assertThat(record.sizeBytes()).isGreaterThan(0);
        assertThat(record.sha256()).isNotBlank();
        assertThat(record.createdAt()).isNotNull();
    }

    /**
     * For any completed generation task, the packaged ZIP SHALL be a valid ZIP archive
     * that can be opened and contains all the provided files plus the metadata entry.
     *
     * <b>Validates: Requirements 3.6, 14.3, 14.4</b>
     */
    @Property(tries = 100)
    @Label("packageAsZip produces a valid ZIP containing all provided files and metadata")
    void packageAsZip_producesValidZipWithAllFilesAndMetadata(
            @ForAll @AlphaChars @StringLength(min = 3, max = 20) String taskIdSuffix,
            @ForAll @Size(min = 1, max = 4) List<@AlphaChars @StringLength(min = 1, max = 8) String> fileNames
    ) throws IOException {
        String taskId = "tsk_" + taskIdSuffix;
        InMemoryArtifactsPort port = new InMemoryArtifactsPort();
        ArtifactsService service = buildService(port);

        Map<String, byte[]> files = new HashMap<>();
        for (String name : fileNames) {
            files.put(name + ".txt", ("content of " + name).getBytes());
        }

        ArtifactRecord record = service.packageAsZip(taskId, "output.zip", files, Map.of("taskId", taskId));

        byte[] zipBytes = port.getBytes(record.artifactId());
        assertThat(zipBytes).isNotNull().isNotEmpty();

        // Verify it is a valid ZIP and contains expected entries
        Map<String, byte[]> extractedEntries = new HashMap<>();
        try (ZipInputStream zis = new ZipInputStream(new ByteArrayInputStream(zipBytes))) {
            ZipEntry entry;
            while ((entry = zis.getNextEntry()) != null) {
                extractedEntries.put(entry.getName(), zis.readAllBytes());
                zis.closeEntry();
            }
        }

        // Metadata entry must always be present
        assertThat(extractedEntries).containsKey(".autocode-metadata.properties");
        String metaContent = new String(extractedEntries.get(".autocode-metadata.properties"));
        assertThat(metaContent).contains("taskId=" + taskId);
        assertThat(metaContent).contains("generatedAt=");

        // All provided files must be present
        for (String name : fileNames) {
            assertThat(extractedEntries).containsKey(name + ".txt");
        }
    }

    /**
     * For any completed generation task, the packaged artifact SHALL be accessible
     * via the download use-case (HTTP access), returning the same bytes that were stored.
     *
     * <b>Validates: Requirements 3.6, 14.2</b>
     */
    @Property(tries = 50)
    @Label("packaged artifact is accessible via download use-case")
    void packagedArtifact_isAccessibleViaDownload(
            @ForAll @AlphaChars @StringLength(min = 3, max = 20) String taskIdSuffix,
            @ForAll @AlphaChars @StringLength(min = 1, max = 8) String fileBaseName
    ) throws IOException {
        String taskId = "tsk_" + taskIdSuffix;
        InMemoryArtifactsPort port = new InMemoryArtifactsPort();
        ArtifactsService service = buildService(port);

        Map<String, byte[]> files = Map.of(fileBaseName + ".py", ("print('hello')").getBytes());
        ArtifactRecord stored = service.packageAsZip(taskId, "app.zip", files, null);

        // Download the artifact — this exercises the HTTP access path
        ArtifactContent content = service.download(taskId, stored.artifactId(), "any-token");

        assertThat(content).isNotNull();
        assertThat(content.record().artifactId()).isEqualTo(stored.artifactId());
        assertThat(content.record().contentType()).isEqualTo("application/zip");

        byte[] downloadedBytes = content.stream().readAllBytes();
        byte[] originalBytes = port.getBytes(stored.artifactId());
        assertThat(downloadedBytes).isEqualTo(originalBytes);
    }

    /**
     * For any completed generation task, the artifact record SHALL carry a unique identifier,
     * a non-null creation timestamp, and the correct task association.
     *
     * <b>Validates: Requirements 14.1, 14.4</b>
     */
    @Property(tries = 100)
    @Label("every packaged artifact has a unique ID, timestamp, and correct task association")
    void packagedArtifact_hasUniqueIdTimestampAndTaskAssociation(
            @ForAll @AlphaChars @StringLength(min = 3, max = 20) String taskIdSuffix,
            @ForAll @AlphaChars @StringLength(min = 1, max = 8) String fileBaseName
    ) {
        String taskId = "tsk_" + taskIdSuffix;
        InMemoryArtifactsPort port = new InMemoryArtifactsPort();
        ArtifactsService service = buildService(port);

        Map<String, byte[]> files = Map.of(fileBaseName + ".py", "# generated".getBytes());
        ArtifactRecord record = service.packageAsZip(taskId, "artifact.zip", files, Map.of("generator", "backend"));

        assertThat(record.artifactId()).isNotBlank();
        assertThat(record.taskId()).isEqualTo(taskId);
        assertThat(record.createdAt()).isNotNull();
        assertThat(record.createdAt()).isBeforeOrEqualTo(Instant.now());
        assertThat(record.name()).isEqualTo("artifact.zip");
    }

    /**
     * For any completed generation task, the artifact SHALL appear in the task's artifact list
     * after packaging, confirming it is stored with a unique identifier.
     *
     * <b>Validates: Requirements 14.1</b>
     */
    @Property(tries = 50)
    @Label("packaged artifact appears in task artifact list")
    void packagedArtifact_appearsInTaskArtifactList(
            @ForAll @AlphaChars @StringLength(min = 3, max = 20) String taskIdSuffix,
            @ForAll @AlphaChars @StringLength(min = 1, max = 8) String fileBaseName
    ) {
        String taskId = "tsk_" + taskIdSuffix;
        InMemoryArtifactsPort port = new InMemoryArtifactsPort();
        ArtifactsService service = buildService(port);

        Map<String, byte[]> files = Map.of(fileBaseName + ".py", "# code".getBytes());
        ArtifactRecord stored = service.packageAsZip(taskId, "result.zip", files, null);

        List<ArtifactRecord> listed = service.list(taskId);

        assertThat(listed).isNotEmpty();
        assertThat(listed).anyMatch(r -> r.artifactId().equals(stored.artifactId()));
    }

    /**
     * Attempting to package an empty file map SHALL throw an IllegalArgumentException,
     * ensuring the service never stores empty/invalid artifacts.
     *
     * <b>Validates: Requirements 3.6</b>
     */
    @Property(tries = 30)
    @Label("packageAsZip rejects empty file maps")
    void packageAsZip_rejectsEmptyFileMaps(
            @ForAll @AlphaChars @StringLength(min = 3, max = 20) String taskIdSuffix
    ) {
        String taskId = "tsk_" + taskIdSuffix;
        InMemoryArtifactsPort port = new InMemoryArtifactsPort();
        ArtifactsService service = buildService(port);

        assertThatThrownBy(() -> service.packageAsZip(taskId, "empty.zip", Map.of(), null))
                .isInstanceOf(IllegalArgumentException.class);
    }

    /**
     * For any artifact stored with a ZIP content-type, the download response SHALL
     * preserve the content-type header as application/zip.
     *
     * <b>Validates: Requirements 14.2</b>
     */
    @Property(tries = 50)
    @Label("downloaded ZIP artifact preserves application/zip content-type")
    void downloadedZipArtifact_preservesContentType(
            @ForAll @AlphaChars @StringLength(min = 3, max = 20) String taskIdSuffix,
            @ForAll @AlphaChars @StringLength(min = 1, max = 8) String fileBaseName
    ) {
        String taskId = "tsk_" + taskIdSuffix;
        InMemoryArtifactsPort port = new InMemoryArtifactsPort();
        ArtifactsService service = buildService(port);

        Map<String, byte[]> files = Map.of(fileBaseName + ".py", "# code".getBytes());
        ArtifactRecord stored = service.packageAsZip(taskId, "app.zip", files, null);

        ArtifactContent content = service.download(taskId, stored.artifactId(), "token");

        assertThat(content.record().contentType()).isEqualTo("application/zip");
    }

    /**
     * For any artifact, the retention policy SHALL correctly identify artifacts
     * that have exceeded the free-tier retention window (30 days).
     *
     * <b>Validates: Requirements 14.5</b>
     */
    @Property(tries = 50)
    @Label("retention policy correctly identifies expired artifacts for free tier")
    void retentionPolicy_correctlyIdentifiesExpiredArtifacts(
            @ForAll @AlphaChars @StringLength(min = 3, max = 20) String taskIdSuffix
    ) {
        String taskId = "tsk_" + taskIdSuffix;

        // Build a port that returns one fresh and one expired artifact
        ArtifactsPort port = mock(ArtifactsPort.class);
        TaskReadPort taskReadPort = mock(TaskReadPort.class);
        when(taskReadPort.exists(taskId)).thenReturn(true);

        Instant now = Instant.now();
        Instant expired = now.minus(31, java.time.temporal.ChronoUnit.DAYS);
        Instant fresh = now.minus(1, java.time.temporal.ChronoUnit.DAYS);

        ArtifactRecord expiredRecord = new ArtifactRecord("art_old", taskId, "old.zip", "application/zip", 100, "sha1", expired);
        ArtifactRecord freshRecord = new ArtifactRecord("art_new", taskId, "new.zip", "application/zip", 100, "sha2", fresh);

        when(port.listByTask(taskId)).thenReturn(List.of(expiredRecord, freshRecord));

        ArtifactsService service = new ArtifactsService(
                port,
                mock(DownloadAuthzPort.class),
                mock(AuditPort.class),
                taskReadPort,
                mock(ProjectAuthz.class)
        );

        List<ArtifactRecord> expired30Days = service.findExpiredArtifacts(taskId, ArtifactsService.RetentionTier.FREE);

        assertThat(expired30Days).hasSize(1);
        assertThat(expired30Days.get(0).artifactId()).isEqualTo("art_old");
    }
}
