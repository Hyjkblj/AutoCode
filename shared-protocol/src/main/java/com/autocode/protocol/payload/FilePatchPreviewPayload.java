package com.autocode.protocol.payload;

import java.util.ArrayList;
import java.util.List;

/**
 * Payload for {@code EventType.FILE_PATCH_PREVIEW}.
 *
 * Either {@code patch} OR {@code files} should be present.
 */
public class FilePatchPreviewPayload {
    /**
     * Optional. End-to-end trace correlation id.
     */
    private String traceId;

    /**
     * Optional. Runtime execution correlation id.
     */
    private String runId;

    /**
     * Suggested values: unified | files.
     */
    private String format;

    /**
     * Optional. Unified diff text (can be truncated by producer).
     */
    private String patch;

    /**
     * Optional. Structured file change list (preferred when patch is large).
     */
    private List<FileChange> files = new ArrayList<>();

    /**
     * Optional. Hash of the preview content (e.g. sha256 over patch or normalized file list).
     */
    private String previewHash;

    public String getTraceId() {
        return traceId;
    }

    public void setTraceId(String traceId) {
        this.traceId = traceId;
    }

    public String getRunId() {
        return runId;
    }

    public void setRunId(String runId) {
        this.runId = runId;
    }

    public String getFormat() {
        return format;
    }

    public void setFormat(String format) {
        this.format = format;
    }

    public String getPatch() {
        return patch;
    }

    public void setPatch(String patch) {
        this.patch = patch;
    }

    public List<FileChange> getFiles() {
        return files;
    }

    public void setFiles(List<FileChange> files) {
        this.files = files;
    }

    public String getPreviewHash() {
        return previewHash;
    }

    public void setPreviewHash(String previewHash) {
        this.previewHash = previewHash;
    }

    public static class FileChange {
        private String path;
        /**
         * Suggested values: add | modify | delete | rename
         */
        private String changeType;
        private String beforeHash;
        private String afterHash;

        public String getPath() {
            return path;
        }

        public void setPath(String path) {
            this.path = path;
        }

        public String getChangeType() {
            return changeType;
        }

        public void setChangeType(String changeType) {
            this.changeType = changeType;
        }

        public String getBeforeHash() {
            return beforeHash;
        }

        public void setBeforeHash(String beforeHash) {
            this.beforeHash = beforeHash;
        }

        public String getAfterHash() {
            return afterHash;
        }

        public void setAfterHash(String afterHash) {
            this.afterHash = afterHash;
        }
    }
}

