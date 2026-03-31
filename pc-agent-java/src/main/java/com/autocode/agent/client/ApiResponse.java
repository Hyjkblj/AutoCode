/**
 * Generic API response envelope used by the agent client.
 */
package com.autocode.agent.client;

public class ApiResponse<T> {
    private boolean ok;
    private T payload;
    private String error;

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
