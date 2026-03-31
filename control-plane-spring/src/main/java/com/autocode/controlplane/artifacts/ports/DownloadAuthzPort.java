package com.autocode.controlplane.artifacts.ports;

public interface DownloadAuthzPort {
    boolean canDownload(String taskId, String artifactId, String presentedToken);
}

