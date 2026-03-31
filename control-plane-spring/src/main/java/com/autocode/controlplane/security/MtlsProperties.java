package com.autocode.controlplane.security;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "mvp.mtls")
public class MtlsProperties {
    /**
     * When true, agent endpoints must present a valid client certificate.
     * This is enforced at the application layer (per-path), so operators are not forced into mTLS.
     */
    private boolean requiredForAgent = false;

    public boolean isRequiredForAgent() {
        return requiredForAgent;
    }

    public void setRequiredForAgent(boolean requiredForAgent) {
        this.requiredForAgent = requiredForAgent;
    }
}

