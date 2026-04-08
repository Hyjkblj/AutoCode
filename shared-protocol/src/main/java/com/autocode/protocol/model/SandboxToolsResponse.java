package com.autocode.protocol.model;

import java.util.ArrayList;
import java.util.List;

/**
 * Response body for {@code GET /sandbox/tools}.
 */
public class SandboxToolsResponse {
    private boolean ok;
    private List<ToolManifest> tools = new ArrayList<>();

    public static SandboxToolsResponse of(List<ToolManifest> tools) {
        SandboxToolsResponse response = new SandboxToolsResponse();
        response.ok = true;
        if (tools != null) {
            response.tools = new ArrayList<>(tools);
        }
        return response;
    }

    public boolean isOk() {
        return ok;
    }

    public void setOk(boolean ok) {
        this.ok = ok;
    }

    public List<ToolManifest> getTools() {
        return tools;
    }

    public void setTools(List<ToolManifest> tools) {
        this.tools = tools;
    }
}
