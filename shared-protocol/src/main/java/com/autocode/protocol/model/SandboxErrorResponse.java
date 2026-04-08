package com.autocode.protocol.model;

/**
 * Error response body used by sandbox HTTP endpoints.
 */
public class SandboxErrorResponse {
    private boolean ok;
    private String status;
    private String error;

    public static SandboxErrorResponse of(String status, String error) {
        SandboxErrorResponse response = new SandboxErrorResponse();
        response.ok = false;
        response.status = status;
        response.error = error;
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

    public String getError() {
        return error;
    }

    public void setError(String error) {
        this.error = error;
    }
}
