package com.autocode.controlplane.artifacts.adapters.auth;

import com.autocode.controlplane.artifacts.ports.DownloadAuthzPort;
import com.autocode.controlplane.security.SecurityPrincipalUtils;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
public class SharedTokenDownloadAuthzAdapter implements DownloadAuthzPort {
    private final String sharedToken;
    private final boolean allowAuthenticatedWithoutSharedToken;

    public SharedTokenDownloadAuthzAdapter(
            @Value("${artifacts.download.shared-token:}") String sharedToken,
            @Value("${artifacts.download.allow-authenticated-without-shared-token:true}") boolean allowAuthenticatedWithoutSharedToken
    ) {
        this.sharedToken = sharedToken == null ? "" : sharedToken.trim();
        this.allowAuthenticatedWithoutSharedToken = allowAuthenticatedWithoutSharedToken;
    }

    @Override
    public boolean canDownload(String taskId, String artifactId, String presentedToken) {
        // Mobile/web authenticated members already pass task-level authorization at controller layer.
        // In that case we allow preview/download by default unless explicitly forced to shared-token mode.
        if (allowAuthenticatedWithoutSharedToken && SecurityPrincipalUtils.currentUsernameOrNull() != null) {
            return true;
        }
        if (sharedToken.isBlank()) {
            return false; // default deny
        }
        if (presentedToken == null || presentedToken.isBlank()) {
            return false;
        }
        return sharedToken.equals(presentedToken.trim());
    }
}

