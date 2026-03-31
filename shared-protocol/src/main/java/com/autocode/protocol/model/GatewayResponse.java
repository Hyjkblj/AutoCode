/**
 * Minimal gateway-style response envelope for future WebSocket protocol work.
 */
package com.autocode.protocol.model;

import java.util.Map;

public class GatewayResponse {
    private String type = "res";
    private String id;
    private boolean ok;
    private Map<String, Object> payload;
    private String error;

    public String getType() {
        return type;
    }

    public void setType(String type) {
        this.type = type;
    }

    public String getId() {
        return id;
    }

    public void setId(String id) {
        this.id = id;
    }

    public boolean isOk() {
        return ok;
    }

    public void setOk(boolean ok) {
        this.ok = ok;
    }

    public Map<String, Object> getPayload() {
        return payload;
    }

    public void setPayload(Map<String, Object> payload) {
        this.payload = payload;
    }

    public String getError() {
        return error;
    }

    public void setError(String error) {
        this.error = error;
    }
}
