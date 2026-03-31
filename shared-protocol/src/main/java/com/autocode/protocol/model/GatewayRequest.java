/**
 * Minimal gateway-style request envelope (req/res/event) for future WebSocket protocol work.
 */
package com.autocode.protocol.model;

import java.util.Map;

public class GatewayRequest {
    private String type = "req";
    private String id;
    private String method;
    private Map<String, Object> params;

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

    public String getMethod() {
        return method;
    }

    public void setMethod(String method) {
        this.method = method;
    }

    public Map<String, Object> getParams() {
        return params;
    }

    public void setParams(Map<String, Object> params) {
        this.params = params;
    }
}
