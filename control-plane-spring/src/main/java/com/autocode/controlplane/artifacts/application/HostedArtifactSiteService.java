package com.autocode.controlplane.artifacts.application;

import com.autocode.controlplane.artifacts.domain.ArtifactContent;
import com.autocode.controlplane.artifacts.domain.ArtifactRecord;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaTypeFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.time.Instant;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.Optional;
import java.util.Properties;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import java.util.stream.Stream;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

@Service
public class HostedArtifactSiteService {
    private static final String META_FILE = ".autocode-site-meta.properties";
    private static final String META_ENTRY_PATH = "entryPath";
    private static final String META_ARTIFACT_SHA = "artifactSha256";
    private static final String DEFAULT_ENTRY = "index.html";

    private final ArtifactsService artifactsService;
    private final Path baseDir;
    private final ConcurrentMap<String, Object> materializeLocks = new ConcurrentHashMap<>();

    public HostedArtifactSiteService(
            ArtifactsService artifactsService,
            @Value("${artifacts.hosting.base-dir:./data/artifacts-hosted}") String baseDir
    ) {
        this.artifactsService = artifactsService;
        this.baseDir = Path.of(baseDir == null ? "./data/artifacts-hosted" : baseDir).toAbsolutePath().normalize();
    }

    @Transactional(readOnly = true)
    public HostedSiteInfo ensureHostedSite(String taskId, String artifactId, String token) {
        artifactsService.assertHostedSiteAccess(taskId, artifactId, token);
        Path siteDir = siteDir(taskId, artifactId);
        HostedSiteInfo cached = readReadySite(siteDir);
        if (cached != null) {
            return cached;
        }

        String lockKey = taskId + ":" + artifactId;
        Object lock = materializeLocks.computeIfAbsent(lockKey, ignored -> new Object());
        synchronized (lock) {
            HostedSiteInfo recheck = readReadySite(siteDir);
            if (recheck != null) {
                return recheck;
            }
            ArtifactContent content = artifactsService.openHostedSite(taskId, artifactId, token);
            try (InputStream in = content.stream()) {
                materializeSite(siteDir, content.record(), in);
            } catch (IOException ex) {
                throw new IllegalStateException("failed to materialize hosted site", ex);
            }
            HostedSiteInfo ready = readReadySite(siteDir);
            if (ready == null) {
                throw new IllegalStateException("hosted site metadata missing after materialization");
            }
            return ready;
        }
    }

    @Transactional(readOnly = true)
    public HostedFile resolveHostedFile(String taskId, String artifactId, String relativePath, String token) {
        HostedSiteInfo site = ensureHostedSite(taskId, artifactId, token);
        Path siteDir = site.rootDir();
        String normalized = sanitizeRelativePath(relativePath);
        String effective = normalized.isBlank() ? site.entryPath() : normalized;

        Path candidate = siteDir.resolve(effective).normalize();
        if (!candidate.startsWith(siteDir)) {
            throw new ArtifactNotFoundException("artifact not found");
        }
        if (Files.isDirectory(candidate)) {
            candidate = candidate.resolve(DEFAULT_ENTRY).normalize();
        }

        if (!Files.exists(candidate) || !Files.isRegularFile(candidate)) {
            Path fallback = siteDir.resolve(site.entryPath()).normalize();
            if (looksLikeSpaRoute(effective)
                    && fallback.startsWith(siteDir)
                    && Files.exists(fallback)
                    && Files.isRegularFile(fallback)) {
                candidate = fallback;
            } else {
                throw new ArtifactNotFoundException("artifact not found");
            }
        }

        String contentType = detectContentType(candidate);
        return new HostedFile(candidate, contentType);
    }

    private String detectContentType(Path file) {
        try {
            String probed = Files.probeContentType(file);
            if (probed != null && !probed.isBlank()) {
                return probed;
            }
        } catch (IOException ignored) {
            // Fallback to extension-based sniffing below.
        }
        Optional<String> guessed = MediaTypeFactory.getMediaType(file.getFileName().toString()).map(Object::toString);
        return guessed.orElse("application/octet-stream");
    }

    private Path siteDir(String taskId, String artifactId) {
        if (taskId == null || taskId.isBlank()) {
            throw new IllegalArgumentException("taskId is required");
        }
        if (artifactId == null || artifactId.isBlank()) {
            throw new IllegalArgumentException("artifactId is required");
        }
        Path dir = baseDir.resolve(taskId).resolve(artifactId).toAbsolutePath().normalize();
        if (!dir.startsWith(baseDir)) {
            throw new IllegalArgumentException("invalid hosted site path");
        }
        return dir;
    }

    private HostedSiteInfo readReadySite(Path siteDir) {
        Path metaPath = siteDir.resolve(META_FILE).normalize();
        if (!metaPath.startsWith(siteDir) || !Files.exists(metaPath) || !Files.isRegularFile(metaPath)) {
            return null;
        }
        Properties props = new Properties();
        try (InputStream in = Files.newInputStream(metaPath)) {
            props.load(in);
        } catch (IOException ex) {
            return null;
        }
        String entryPath = sanitizeRelativePath(props.getProperty(META_ENTRY_PATH, ""));
        if (entryPath.isBlank()) {
            return null;
        }
        Path entryFile = siteDir.resolve(entryPath).normalize();
        if (!entryFile.startsWith(siteDir) || !Files.exists(entryFile) || !Files.isRegularFile(entryFile)) {
            return null;
        }
        return new HostedSiteInfo(siteDir, entryPath);
    }

    private void materializeSite(Path siteDir, ArtifactRecord record, InputStream artifactStream) throws IOException {
        resetDirectory(siteDir);
        if (isZipArtifact(record)) {
            unzipToDirectory(artifactStream, siteDir);
        } else {
            writeSinglePageArtifact(siteDir, record, artifactStream);
        }
        String entryPath = detectEntryPath(siteDir);
        writeMetadata(siteDir, entryPath, record);
    }

    private boolean isZipArtifact(ArtifactRecord record) {
        String name = record.name() == null ? "" : record.name().trim().toLowerCase(Locale.ROOT);
        String ct = record.contentType() == null ? "" : record.contentType().trim().toLowerCase(Locale.ROOT);
        return name.endsWith(".zip") || ct.contains("zip");
    }

    private void unzipToDirectory(InputStream source, Path siteDir) throws IOException {
        boolean hasFile = false;
        try (ZipInputStream zis = new ZipInputStream(source)) {
            ZipEntry entry;
            while ((entry = zis.getNextEntry()) != null) {
                String cleanName = sanitizeZipEntry(entry.getName());
                if (cleanName.isBlank()) {
                    zis.closeEntry();
                    continue;
                }
                Path out = siteDir.resolve(cleanName).normalize();
                if (!out.startsWith(siteDir)) {
                    throw new IllegalArgumentException("invalid zip entry path");
                }
                if (entry.isDirectory()) {
                    Files.createDirectories(out);
                } else {
                    Path parent = out.getParent();
                    if (parent != null) {
                        Files.createDirectories(parent);
                    }
                    try (OutputStream os = Files.newOutputStream(out)) {
                        zis.transferTo(os);
                    }
                    hasFile = true;
                }
                zis.closeEntry();
            }
        }
        if (!hasFile) {
            throw new IllegalArgumentException("zip artifact has no files");
        }
    }

    private void writeSinglePageArtifact(Path siteDir, ArtifactRecord record, InputStream source) throws IOException {
        String originalName = record.name() == null ? "" : record.name().trim();
        String rawName = originalName.isBlank() ? DEFAULT_ENTRY : originalName;
        String candidate;
        try {
            candidate = Path.of(rawName).getFileName().toString();
        } catch (RuntimeException ex) {
            candidate = DEFAULT_ENTRY;
        }
        String lowered = candidate.toLowerCase(Locale.ROOT);
        if (!lowered.endsWith(".html") && !lowered.endsWith(".htm")) {
            candidate = DEFAULT_ENTRY;
        }
        Path out = siteDir.resolve(candidate).normalize();
        if (!out.startsWith(siteDir)) {
            throw new IllegalArgumentException("invalid artifact file name");
        }
        Path parent = out.getParent();
        if (parent != null) {
            Files.createDirectories(parent);
        }
        Files.copy(source, out, StandardCopyOption.REPLACE_EXISTING);
    }

    private String detectEntryPath(Path siteDir) throws IOException {
        Path rootIndex = siteDir.resolve(DEFAULT_ENTRY).normalize();
        if (rootIndex.startsWith(siteDir) && Files.exists(rootIndex) && Files.isRegularFile(rootIndex)) {
            return DEFAULT_ENTRY;
        }
        try (Stream<Path> stream = Files.walk(siteDir)) {
            List<Path> htmlFiles = stream
                    .filter(Files::isRegularFile)
                    .filter(path -> {
                        String name = path.getFileName().toString().toLowerCase(Locale.ROOT);
                        return name.endsWith(".html") || name.endsWith(".htm");
                    })
                    .sorted()
                    .toList();
            if (!htmlFiles.isEmpty()) {
                return toUnixRelativePath(siteDir, htmlFiles.get(0));
            }
        }
        throw new IllegalArgumentException("hosted site requires an html entry file");
    }

    private void writeMetadata(Path siteDir, String entryPath, ArtifactRecord record) throws IOException {
        Properties props = new Properties();
        props.setProperty(META_ENTRY_PATH, entryPath);
        props.setProperty(META_ARTIFACT_SHA, record.sha256() == null ? "" : record.sha256());
        props.setProperty("generatedAt", Instant.now().toString());
        Path metaPath = siteDir.resolve(META_FILE).normalize();
        if (!metaPath.startsWith(siteDir)) {
            throw new IllegalArgumentException("invalid hosted site metadata path");
        }
        try (OutputStream out = Files.newOutputStream(metaPath)) {
            props.store(out, "AutoCode hosted artifact metadata");
        }
    }

    private void resetDirectory(Path siteDir) throws IOException {
        if (Files.exists(siteDir)) {
            if (!siteDir.startsWith(baseDir)) {
                throw new IllegalArgumentException("refusing to clear directory outside hosting base");
            }
            try (Stream<Path> walk = Files.walk(siteDir)) {
                List<Path> paths = walk.sorted(Comparator.reverseOrder()).toList();
                for (Path path : paths) {
                    Files.deleteIfExists(path);
                }
            }
        }
        Files.createDirectories(siteDir);
    }

    private String sanitizeZipEntry(String entryName) {
        if (entryName == null) {
            return "";
        }
        String normalized = entryName.replace('\\', '/').trim();
        while (normalized.startsWith("/")) {
            normalized = normalized.substring(1);
        }
        return sanitizeRelativePath(normalized);
    }

    private String sanitizeRelativePath(String path) {
        if (path == null) {
            return "";
        }
        String normalized = path.replace('\\', '/').trim();
        while (normalized.startsWith("/")) {
            normalized = normalized.substring(1);
        }
        if (normalized.isBlank()) {
            return "";
        }
        Path clean;
        try {
            clean = Path.of(normalized).normalize();
        } catch (RuntimeException ex) {
            return "";
        }
        String unix = clean.toString().replace('\\', '/');
        if (unix.equals(".") || unix.startsWith("..") || unix.contains("/../")) {
            return "";
        }
        return unix;
    }

    private boolean looksLikeSpaRoute(String relativePath) {
        if (relativePath == null || relativePath.isBlank()) {
            return false;
        }
        String clean = sanitizeRelativePath(relativePath);
        if (clean.isBlank()) {
            return false;
        }
        String leaf = clean.substring(clean.lastIndexOf('/') + 1);
        return !leaf.contains(".");
    }

    private String toUnixRelativePath(Path root, Path child) {
        return root.relativize(child).toString().replace('\\', '/');
    }

    public record HostedSiteInfo(Path rootDir, String entryPath) {
    }

    public record HostedFile(Path filePath, String contentType) {
    }
}
