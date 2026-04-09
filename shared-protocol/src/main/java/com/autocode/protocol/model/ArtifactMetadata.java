package com.autocode.protocol.model;

import java.util.List;

/**
 * Artifact metadata DTO (B stage: zip export).
 */
public class ArtifactMetadata {
    private String artifactId;
    private String hash;
    /** Optional hash alias (preferred for nl2web contracts). */
    private String sha256;
    private Long size;
    private String mime;
    /** Optional mime alias (preferred for nl2web contracts). */
    private String mimeType;
    private String type;
    /** Optional human label (e.g. file name). */
    private String name;
    /** Optional file name alias (preferred for nl2web contracts). */
    private String fileName;
    /** Optional direct download URL when hosted. */
    private String downloadUrl;
    /** Optional primary entry path inside a bundle (zip, etc.). */
    private String entryPath;
    /** Optional reproducible build hint. */
    private BuildDescriptor build;
    /** Optional run hint for operators. */
    private RunDescriptor run;

    public String getArtifactId() {
        return artifactId;
    }

    public void setArtifactId(String artifactId) {
        this.artifactId = artifactId;
    }

    public String getHash() {
        return coalesce(hash, sha256);
    }

    public void setHash(String hash) {
        this.hash = hash;
        if (!isBlank(hash)) {
            this.sha256 = hash;
        }
    }

    public String getSha256() {
        return coalesce(sha256, hash);
    }

    public void setSha256(String sha256) {
        this.sha256 = sha256;
        if (!isBlank(sha256) && isBlank(this.hash)) {
            this.hash = sha256;
        }
    }

    public Long getSize() {
        return size;
    }

    public void setSize(Long size) {
        this.size = size;
    }

    public String getMime() {
        return coalesce(mime, mimeType);
    }

    public void setMime(String mime) {
        this.mime = mime;
        if (!isBlank(mime)) {
            this.mimeType = mime;
        }
    }

    public String getMimeType() {
        return coalesce(mimeType, mime);
    }

    public void setMimeType(String mimeType) {
        this.mimeType = mimeType;
        if (!isBlank(mimeType) && isBlank(this.mime)) {
            this.mime = mimeType;
        }
    }

    public String getType() {
        return type;
    }

    public void setType(String type) {
        this.type = type;
    }

    public String getName() {
        return coalesce(name, fileName);
    }

    public void setName(String name) {
        this.name = name;
        if (!isBlank(name)) {
            this.fileName = name;
        }
    }

    public String getFileName() {
        return coalesce(fileName, name);
    }

    public void setFileName(String fileName) {
        this.fileName = fileName;
        if (!isBlank(fileName) && isBlank(this.name)) {
            this.name = fileName;
        }
    }

    public String getDownloadUrl() {
        return downloadUrl;
    }

    public void setDownloadUrl(String downloadUrl) {
        this.downloadUrl = downloadUrl;
    }

    public String getEntryPath() {
        return entryPath;
    }

    public void setEntryPath(String entryPath) {
        this.entryPath = entryPath;
    }

    public BuildDescriptor getBuild() {
        return build;
    }

    public void setBuild(BuildDescriptor build) {
        this.build = build;
    }

    public RunDescriptor getRun() {
        return run;
    }

    public void setRun(RunDescriptor run) {
        this.run = run;
    }

    public static class BuildDescriptor {
        private String command;
        private String workingDir;

        public String getCommand() {
            return command;
        }

        public void setCommand(String command) {
            this.command = command;
        }

        public String getWorkingDir() {
            return workingDir;
        }

        public void setWorkingDir(String workingDir) {
            this.workingDir = workingDir;
        }
    }

    public static class RunDescriptor {
        private String command;
        private List<String> hints;

        public String getCommand() {
            return command;
        }

        public void setCommand(String command) {
            this.command = command;
        }

        public List<String> getHints() {
            return hints;
        }

        public void setHints(List<String> hints) {
            this.hints = hints;
        }
    }

    private static String coalesce(String primary, String fallback) {
        return !isBlank(primary) ? primary : fallback;
    }

    private static boolean isBlank(String value) {
        return value == null || value.trim().isEmpty();
    }
}

