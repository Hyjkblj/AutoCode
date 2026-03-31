package com.autocode.controlplane.api;

import com.autocode.protocol.model.GatewayResponse;

import java.util.Map;

public final class GatewayResponses {
    private GatewayResponses() {
    }

    public static GatewayResponse ok(Map<String, Object> payload) {
        GatewayResponse res = new GatewayResponse();
        res.setOk(true);
        res.setPayload(payload);
        return res;
    }

    public static GatewayResponse error(String message) {
        GatewayResponse res = new GatewayResponse();
        res.setOk(false);
        res.setError(message);
        return res;
    }
}

