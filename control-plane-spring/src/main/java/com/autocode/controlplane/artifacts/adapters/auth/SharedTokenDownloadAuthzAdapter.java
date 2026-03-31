package com.autocode.controlplane.artifacts.adapters.auth;

import com.autocode.controlplane.artifacts.ports.DownloadAuthzPort;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
public class SharedTokenDownloadAuthzAdapter implements DownloadAuthzPort {
    private final String sharedToken;

    public SharedTokenDownloadAuthzAdapter(@Value("${artifacts.download.shared-token:}") String sharedToken) {
        this.sharedToken = sharedToken == null ? "" : sharedToken.trim();
    }

    @Override
    public boolean canDownload(String taskId, String artifactId, String presentedToken) {
        if (sharedToken.isBlank()) {
            return false; // default deny
        }
        if (presentedToken == null || presentedToken.isBlank()) {
            return false;
        }
        return sharedToken.equals(presentedToken.trim());
    }
}

