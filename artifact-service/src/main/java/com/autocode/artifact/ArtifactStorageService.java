package com.autocode.artifact;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.io.BufferedInputStream;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

/**
 * Core artifact storage and lifecycle service.
 *
 * Handles:
 *  - Storing raw binary artifacts to local filesystem + DB metadata (14.1, 14.2)
 *  - Packaging files into ZIP archives with metadata entry (14.3, 14.4)
 *  - Retention policy enforcement (14.5)
 *  - Access audit logging (14.6)
 *
 * Requirements: 11.1, 11.2, 14.1–14.7
 */
@Service
public class ArtifactStorageService {

    private static final Logger log = LoggerFactory.getLogger(ArtifactStorageService.class);

    /**
     * Retention tier for artifact lifecycle management.
     * Requirements 14.5: 30 days for free tier, 1 year for premium.
     */
    public enum RetentionTier {
        FREE(30),
        PREMIUM(365);

        private final int retentionDays;

        RetentionTier(int days) { this.retentionDays = days; }

        public int getRetentionDays() { return retentionDays; }
    }

    private final ArtifactRepository artifactRepository;
    private final Path baseDir;

    public ArtifactStorageService(
            ArtifactRepository artifactRepository,
            @Value("${artifacts.storage.base-dir:./data/artifacts}") String baseDir
    ) {
        this.artifactRepository = artifactRepository;
        this.baseDir = Path.of(baseDir == null ? "./data/artifacts" : baseDir).toAbsolutePath().normalize();
    }

    // -------------------------------------------------------------------------
    // Store
    // -------------------------------------------------------------------------

    /**
     * Store a binary artifact for a task.
     *
     * @param taskId      owning task identifier
     * @param name        human-readable file name
     * @param contentType MIME type
     * @param data        artifact bytes
     * @return persisted artifact metadata
     */
    @Transactional
    public ArtifactEntity store(String taskId, String name, String contentType, InputStream data) {
        requireNonBlank(taskId, "taskId");
        if (data == null) throw new IllegalArgumentException("data is required");

        String artifactId = "art_" + UUID.randomUUID().toString().replace("-", "");
        Instant now = Instant.now();
        String safeName = (name == null || name.isBlank()) ? artifactId : name.trim();

        Path taskDir = resolveTaskDir(taskId);
        try {
            Files.createDirectories(taskDir);
            Path tmp = taskDir.resolve(artifactId + ".tmp");
            Path out = taskDir.resolve(artifactId);

            DigestResult digest = copyAndHash(data, tmp);
            Files.move(tmp, out, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);

            ArtifactEntity entity = new ArtifactEntity();
            entity.setArtifactId(artifactId);
            entity.setTaskId(taskId);
            entity.setName(safeName);
            entity.setContentType(contentType == null ? null : contentType.trim());
            entity.setSizeBytes(digest.sizeBytes());
            entity.setSha256(digest.sha256Hex());
            entity.setStoragePath(out.toString());
            entity.setCreatedAt(now);
            artifactRepository.save(entity);

            log.info("artifact.stored taskId={} artifactId={} name={} sizeBytes={} sha256={}",
                    taskId, artifactId, safeName, digest.sizeBytes(), digest.sha256Hex());
            return entity;
        } catch (IOException ex) {
            throw new IllegalStateException("failed to store artifact", ex);
        }
    }

    // -------------------------------------------------------------------------
    // Package as ZIP
    // -------------------------------------------------------------------------

    /**
     * Package a collection of named files into a ZIP archive and store it.
     *
     * The ZIP includes a {@code .autocode-metadata.properties} entry with generation
     * timestamp and task details (Requirements 14.3, 14.4).
     *
     * @param taskId   owning task
     * @param zipName  desired artifact name (should end with .zip)
     * @param files    map of relative path → file bytes
     * @param metadata additional key/value pairs written into the metadata entry
     * @return stored artifact entity
     */
    @Transactional
    public ArtifactEntity packageAsZip(
            String taskId,
            String zipName,
            Map<String, byte[]> files,
            Map<String, String> metadata
    ) {
        requireNonBlank(taskId, "taskId");
        if (files == null || files.isEmpty()) throw new IllegalArgumentException("files must not be empty");
        String safeName = (zipName == null || zipName.isBlank()) ? "artifact.zip" : zipName.trim();
        byte[] zipBytes = buildZip(taskId, files, metadata);
        return store(taskId, safeName, "application/zip", new ByteArrayInputStream(zipBytes));
    }

    // -------------------------------------------------------------------------
    // Read
    // -------------------------------------------------------------------------

    /**
     * List all artifacts for a task, newest first.
     */
    @Transactional(readOnly = true)
    public List<ArtifactEntity> listByTask(String taskId) {
        requireNonBlank(taskId, "taskId");
        return artifactRepository.findByTaskIdOrderByCreatedAtDesc(taskId);
    }

    /**
     * Retrieve artifact metadata by ID.
     *
     * @throws ArtifactNotFoundException if not found or taskId mismatch
     */
    @Transactional(readOnly = true)
    public ArtifactEntity getMetadata(String taskId, String artifactId) {
        requireNonBlank(taskId, "taskId");
        requireNonBlank(artifactId, "artifactId");
        ArtifactEntity entity = artifactRepository.findById(artifactId)
                .orElseThrow(() -> new ArtifactNotFoundException("artifact not found: " + artifactId));
        if (!taskId.equals(entity.getTaskId())) {
            throw new ArtifactNotFoundException("artifact not found: " + artifactId);
        }
        log.info("artifact.accessed taskId={} artifactId={} action=metadata", taskId, artifactId);
        return entity;
    }

    /**
     * Open an artifact for streaming download.
     *
     * @return open {@link InputStream} — caller must close it
     * @throws ArtifactNotFoundException if not found or taskId mismatch
     */
    @Transactional(readOnly = true)
    public ArtifactStream open(String taskId, String artifactId) {
        ArtifactEntity entity = getMetadata(taskId, artifactId);
        try {
            InputStream stream = new BufferedInputStream(
                    Files.newInputStream(Path.of(entity.getStoragePath())));
            log.info("artifact.accessed taskId={} artifactId={} action=download sizeBytes={}",
                    taskId, artifactId, entity.getSizeBytes());
            return new ArtifactStream(entity, stream);
        } catch (IOException ex) {
            throw new IllegalStateException("failed to open artifact", ex);
        }
    }

    /**
     * Resolve the owning taskId for a given artifactId without requiring the caller to know it.
     *
     * @param artifactId artifact identifier
     * @return Optional containing the taskId, or empty if not found
     */
    @Transactional(readOnly = true)
    public java.util.Optional<String> findTaskIdByArtifactId(String artifactId) {
        requireNonBlank(artifactId, "artifactId");
        return artifactRepository.findById(artifactId).map(ArtifactEntity::getTaskId);
    }

    // -------------------------------------------------------------------------
    // Delete
    // -------------------------------------------------------------------------

    /**
     * Delete an artifact — removes both the file and the DB record.
     *
     * @throws ArtifactNotFoundException if not found or taskId mismatch
     */
    @Transactional
    public void delete(String taskId, String artifactId) {
        ArtifactEntity entity = getMetadata(taskId, artifactId);
        try {
            Files.deleteIfExists(Path.of(entity.getStoragePath()));
        } catch (IOException ex) {
            log.warn("artifact.delete.file-error taskId={} artifactId={} path={} error={}",
                    taskId, artifactId, entity.getStoragePath(), ex.getMessage());
        }
        artifactRepository.deleteById(artifactId);
        log.info("artifact.deleted taskId={} artifactId={}", taskId, artifactId);
    }

    // -------------------------------------------------------------------------
    // Retention
    // -------------------------------------------------------------------------

    /**
     * Find artifacts that have exceeded the retention window for the given tier.
     *
     * Requirements 14.5: 30 days for free tier, 1 year for premium.
     *
     * @param taskId owning task
     * @param tier   retention tier to apply
     * @return list of expired artifact entities
     */
    @Transactional(readOnly = true)
    public List<ArtifactEntity> findExpired(String taskId, RetentionTier tier) {
        requireNonBlank(taskId, "taskId");
        Instant cutoff = Instant.now().minus(tier.getRetentionDays(), ChronoUnit.DAYS);
        return artifactRepository.findByTaskIdOrderByCreatedAtDesc(taskId).stream()
                .filter(e -> e.getCreatedAt() != null && e.getCreatedAt().isBefore(cutoff))
                .toList();
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    private Path resolveTaskDir(String taskId) {
        Path dir = baseDir.resolve(taskId).normalize();
        if (!dir.startsWith(baseDir)) {
            throw new IllegalArgumentException("invalid taskId path");
        }
        return dir;
    }

    private static DigestResult copyAndHash(InputStream in, Path out) throws IOException {
        MessageDigest digest = sha256();
        long total = 0;
        try (InputStream input = new BufferedInputStream(in);
             var os = Files.newOutputStream(out)) {
            byte[] buf = new byte[8192];
            int n;
            while ((n = input.read(buf)) >= 0) {
                if (n == 0) continue;
                digest.update(buf, 0, n);
                os.write(buf, 0, n);
                total += n;
            }
        }
        return new DigestResult(total, HexFormat.of().formatHex(digest.digest()));
    }

    private static MessageDigest sha256() {
        try {
            return MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 not available", e);
        }
    }

    private static byte[] buildZip(String taskId, Map<String, byte[]> files, Map<String, String> metadata) {
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        try (ZipOutputStream zos = new ZipOutputStream(baos)) {
            // Metadata entry first
            ZipEntry metaEntry = new ZipEntry(".autocode-metadata.properties");
            zos.putNextEntry(metaEntry);
            StringBuilder meta = new StringBuilder();
            meta.append("generatedAt=").append(Instant.now()).append("\n");
            meta.append("taskId=").append(taskId).append("\n");
            if (metadata != null) {
                for (Map.Entry<String, String> e : metadata.entrySet()) {
                    String k = e.getKey().replace("=", "_").replace("\n", "_");
                    String v = e.getValue() == null ? "" : e.getValue().replace("\n", " ");
                    meta.append(k).append("=").append(v).append("\n");
                }
            }
            zos.write(meta.toString().getBytes(StandardCharsets.UTF_8));
            zos.closeEntry();

            // File entries
            for (Map.Entry<String, byte[]> file : files.entrySet()) {
                String entryName = sanitizeZipEntryName(file.getKey());
                if (entryName.isBlank()) continue;
                ZipEntry entry = new ZipEntry(entryName);
                zos.putNextEntry(entry);
                byte[] content = file.getValue();
                if (content != null) zos.write(content);
                zos.closeEntry();
            }
        } catch (IOException ex) {
            throw new IllegalStateException("failed to build ZIP artifact", ex);
        }
        return baos.toByteArray();
    }

    private static String sanitizeZipEntryName(String name) {
        if (name == null) return "";
        String normalized = name.replace('\\', '/').trim();
        while (normalized.startsWith("/")) normalized = normalized.substring(1);
        if (normalized.contains("../") || normalized.equals("..")) return "";
        return normalized;
    }

    private static void requireNonBlank(String value, String field) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(field + " is required");
        }
    }

    // -------------------------------------------------------------------------
    // Value types
    // -------------------------------------------------------------------------

    private record DigestResult(long sizeBytes, String sha256Hex) {}

    /** Pairs artifact metadata with an open stream for streaming responses. */
    public record ArtifactStream(ArtifactEntity entity, InputStream stream) {}
}
