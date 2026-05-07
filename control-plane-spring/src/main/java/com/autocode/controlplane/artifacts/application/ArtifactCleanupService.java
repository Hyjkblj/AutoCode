package com.autocode.controlplane.artifacts.application;

import com.autocode.controlplane.artifacts.domain.ArtifactRecord;
import com.autocode.controlplane.artifacts.ports.ArtifactsPort;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.time.Instant;
import java.util.Comparator;
import java.util.List;
import java.util.stream.Stream;

/**
 * Scheduled cleanup for expired artifacts and stale temp files.
 *
 * <p>Runs daily by default. Retention period is configurable via
 * {@code artifacts.cleanup.retention-days} (default: 30).</p>
 */
@Service
public class ArtifactCleanupService {
    private static final Logger log = LoggerFactory.getLogger(ArtifactCleanupService.class);

    private final ArtifactsPort artifactsPort;
    private final Path hostedBaseDir;
    private final Duration retention;
    private final boolean enabled;

    public ArtifactCleanupService(
            ArtifactsPort artifactsPort,
            @Value("${artifacts.hosting.base-dir:./data/artifacts-hosted}") String hostedBaseDir,
            @Value("${artifacts.cleanup.retention-days:30}") int retentionDays,
            @Value("${artifacts.cleanup.enabled:true}") boolean enabled
    ) {
        this.artifactsPort = artifactsPort;
        this.hostedBaseDir = Path.of(hostedBaseDir == null ? "./data/artifacts-hosted" : hostedBaseDir)
                .toAbsolutePath().normalize();
        this.retention = Duration.ofDays(Math.max(1, retentionDays));
        this.enabled = enabled;
    }

    /**
     * Daily cleanup: remove expired artifacts and stale temp files.
     */
    @Scheduled(cron = "0 3 3 * * *")
    public void dailyCleanup() {
        if (!enabled) {
            return;
        }
        Instant cutoff = Instant.now().minus(retention);
        log.info("artifact cleanup started, cutoff={}", cutoff);

        int expiredCount = cleanupExpiredArtifacts(cutoff);
        int tmpCount = artifactsPort.cleanStaleTmpFiles();

        log.info("artifact cleanup finished: {} expired artifacts removed, {} stale tmp files cleaned",
                expiredCount, tmpCount);
    }

    private int cleanupExpiredArtifacts(Instant cutoff) {
        List<ArtifactRecord> expired = artifactsPort.findExpiredByAge(cutoff);
        int count = 0;
        for (ArtifactRecord record : expired) {
            try {
                artifactsPort.deleteFile(record.taskId(), record.artifactId());
                deleteHostedSite(record.taskId(), record.artifactId());
                count++;
            } catch (Exception ex) {
                log.warn("failed to delete expired artifact {}: {}",
                        record.artifactId(), ex.getMessage());
            }
        }
        return count;
    }

    private void deleteHostedSite(String taskId, String artifactId) {
        Path siteDir = hostedBaseDir.resolve(taskId).resolve(artifactId).normalize();
        if (!siteDir.startsWith(hostedBaseDir)) {
            return;
        }
        if (!Files.exists(siteDir)) {
            return;
        }
        try (Stream<Path> walk = Files.walk(siteDir)) {
            walk.sorted(Comparator.reverseOrder())
                    .forEach(path -> {
                        try {
                            Files.deleteIfExists(path);
                        } catch (IOException ignored) {
                        }
                    });
        } catch (IOException ex) {
            log.debug("failed to delete hosted site {}/{}: {}", taskId, artifactId, ex.getMessage());
        }
    }
}
