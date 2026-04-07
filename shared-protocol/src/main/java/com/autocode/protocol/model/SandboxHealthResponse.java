package com.autocode.protocol.model;

/**
 * Response body for {@code GET /sandbox/health}.
 */
public class SandboxHealthResponse {
    private boolean ok;
    private String status;

    public static SandboxHealthResponse up() {
        SandboxHealthResponse response = new SandboxHealthResponse();
        response.ok = true;
        response.status = "up";
        return response;
    }

    public boolean isOk() {
        return ok;
    }

    public void setOk(boolean ok) {
        this.ok = ok;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }
}
