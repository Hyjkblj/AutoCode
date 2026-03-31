/**
 * Minimal gateway-style event envelope for future WebSocket protocol work.
 */
package com.autocode.protocol.model;

import java.util.Map;

public class GatewayEvent {
    private String type = "event";
    private String event;
    private Map<String, Object> payload;
    private long seq;

    public String getType() {
        return type;
    }

    public void setType(String type) {
        this.type = type;
    }

    public String getEvent() {
        return event;
    }

    public void setEvent(String event) {
        this.event = event;
    }

    public Map<String, Object> getPayload() {
        return payload;
    }

    public void setPayload(Map<String, Object> payload) {
        this.payload = payload;
    }

    public long getSeq() {
        return seq;
    }

    public void setSeq(long seq) {
        this.seq = seq;
    }
}
