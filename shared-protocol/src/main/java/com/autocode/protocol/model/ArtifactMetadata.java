package com.autocode.protocol.model;

import java.util.List;

/**
 * Artifact metadata DTO (B stage: zip export).
 */
public class ArtifactMetadata {
    private String artifactId;
    private String hash;
    private Long size;
    private String mime;
    private String type;
    /** Optional human label (e.g. file name). */
    private String name;
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
        return hash;
    }

    public void setHash(String hash) {
        this.hash = hash;
    }

    public Long getSize() {
        return size;
    }

    public void setSize(Long size) {
        this.size = size;
    }

    public String getMime() {
        return mime;
    }

    public void setMime(String mime) {
        this.mime = mime;
    }

    public String getType() {
        return type;
    }

    public void setType(String type) {
        this.type = type;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
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
}

