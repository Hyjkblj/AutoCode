/**
 * Generic REST response envelope for MVP APIs.
 */
package com.autocode.controlplane.api;

public class ApiResponse<T> {
    private boolean ok;
    private T payload;
    private String error;

    public static <T> ApiResponse<T> ok(T payload) {
        ApiResponse<T> response = new ApiResponse<>();
        response.setOk(true);
        response.setPayload(payload);
        return response;
    }

    public static <T> ApiResponse<T> error(String error) {
        ApiResponse<T> response = new ApiResponse<>();
        response.setOk(false);
        response.setError(error);
        return response;
    }

    public boolean isOk() {
        return ok;
    }

    public void setOk(boolean ok) {
        this.ok = ok;
    }

    public T getPayload() {
        return payload;
    }

    public void setPayload(T payload) {
        this.payload = payload;
    }

    public String getError() {
        return error;
    }

    public void setError(String error) {
        this.error = error;
    }
}
