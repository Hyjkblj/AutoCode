package com.autocode.controlplane.artifacts.adapters.storage;

import com.autocode.controlplane.artifacts.domain.ArtifactContent;
import com.autocode.controlplane.artifacts.domain.ArtifactRecord;
import com.autocode.controlplane.artifacts.ports.ArtifactsPort;
import com.autocode.controlplane.artifacts.application.ArtifactNotFoundException;
import com.autocode.controlplane.persistence.entity.ArtifactEntity;
import com.autocode.controlplane.persistence.repo.ArtifactEntityRepository;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.io.BufferedInputStream;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.HexFormat;
import java.util.List;
import java.util.UUID;

@Component
public class LocalFileArtifactsAdapter implements ArtifactsPort {
    private final ArtifactEntityRepository artifactRepository;
    private final Path baseDir;

    public LocalFileArtifactsAdapter(
            ArtifactEntityRepository artifactRepository,
            @Value("${artifacts.storage.base-dir:./data/artifacts}") String baseDir
    ) {
        this.artifactRepository = artifactRepository;
        this.baseDir = Path.of(baseDir == null ? "./data/artifacts" : baseDir).toAbsolutePath().normalize();
    }

    /**
     * Store bytes to local disk and persist metadata. This is the B-stage default storage adapter.
     */
    @Override
    @Transactional
    public ArtifactRecord store(String taskId, String name, String contentType, InputStream data) {
        if (taskId == null || taskId.isBlank()) throw new IllegalArgumentException("taskId is required");
        if (data == null) throw new IllegalArgumentException("data is required");
        String artifactId = "art_" + UUID.randomUUID().toString().replace("-", "");
        Instant now = Instant.now();
        String safeName = (name == null || name.isBlank()) ? artifactId : name.trim();
        Path taskDir = baseDir.resolve(taskId).normalize();
        if (!taskDir.startsWith(baseDir)) {
            throw new IllegalArgumentException("invalid taskId path");
        }
        try {
            Files.createDirectories(taskDir);
            Path tmp = taskDir.resolve(artifactId + ".tmp");
            Path out = taskDir.resolve(artifactId);

            DigestingCopyResult copy = copyAndHashToFile(data, tmp);
            Files.move(tmp, out, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);

            ArtifactEntity entity = new ArtifactEntity();
            entity.setArtifactId(artifactId);
            entity.setTaskId(taskId);
            entity.setName(safeName);
            entity.setContentType(contentType == null ? null : contentType.trim());
            entity.setSizeBytes(copy.sizeBytes());
            entity.setSha256(copy.sha256Hex());
            entity.setStoragePath(out.toString());
            entity.setCreatedAt(now);
            artifactRepository.save(entity);

            return toRecord(entity);
        } catch (IOException ex) {
            throw new IllegalStateException("failed to store artifact", ex);
        }
    }

    @Override
    @Transactional(readOnly = true)
    public List<ArtifactRecord> listByTask(String taskId) {
        if (taskId == null || taskId.isBlank()) throw new IllegalArgumentException("taskId is required");
        return artifactRepository.findByTaskIdOrderByCreatedAtDesc(taskId).stream().map(this::toRecord).toList();
    }

    @Override
    @Transactional(readOnly = true)
    public ArtifactContent open(String taskId, String artifactId) {
        if (taskId == null || taskId.isBlank()) throw new IllegalArgumentException("taskId is required");
        if (artifactId == null || artifactId.isBlank()) throw new IllegalArgumentException("artifactId is required");
        ArtifactEntity entity = artifactRepository.findById(artifactId).orElseThrow(() -> new ArtifactNotFoundException("artifact not found"));
        if (!taskId.equals(entity.getTaskId())) {
            throw new ArtifactNotFoundException("artifact not found");
        }
        try {
            InputStream stream = new BufferedInputStream(new FileInputStream(entity.getStoragePath()));
            return new ArtifactContent(toRecord(entity), stream);
        } catch (IOException ex) {
            throw new IllegalStateException("failed to open artifact", ex);
        }
    }

    private ArtifactRecord toRecord(ArtifactEntity entity) {
        return new ArtifactRecord(
                entity.getArtifactId(),
                entity.getTaskId(),
                entity.getName(),
                entity.getContentType(),
                entity.getSizeBytes(),
                entity.getSha256(),
                entity.getCreatedAt()
        );
    }

    private record DigestingCopyResult(long sizeBytes, String sha256Hex) {
    }

    private static DigestingCopyResult copyAndHashToFile(InputStream in, Path out) throws IOException {
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
        String hex = HexFormat.of().formatHex(digest.digest());
        return new DigestingCopyResult(total, hex);
    }

    private static MessageDigest sha256() {
        try {
            return MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 not available", e);
        }
    }
}

