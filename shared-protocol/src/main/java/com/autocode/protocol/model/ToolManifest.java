package com.autocode.protocol.model;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * Tool self-description contract used by runtime discovery, approvals, and policy surfaces.
 */
public class ToolManifest {
    private String name;
    private String version;
    private String description;
    private String action;
    /**
     * Optional language-neutral schema fragment for args.
     */
    private Map<String, Object> argsSchema;
    private List<ToolParamSpec> params = new ArrayList<>();
    private ToolPermissions permissions;

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public String getVersion() {
        return version;
    }

    public void setVersion(String version) {
        this.version = version;
    }

    public String getDescription() {
        return description;
    }

    public void setDescription(String description) {
        this.description = description;
    }

    public String getAction() {
        return action;
    }

    public void setAction(String action) {
        this.action = action;
    }

    public Map<String, Object> getArgsSchema() {
        return argsSchema;
    }

    public void setArgsSchema(Map<String, Object> argsSchema) {
        this.argsSchema = argsSchema;
    }

    public List<ToolParamSpec> getParams() {
        return params;
    }

    public void setParams(List<ToolParamSpec> params) {
        this.params = params;
    }

    public ToolPermissions getPermissions() {
        return permissions;
    }

    public void setPermissions(ToolPermissions permissions) {
        this.permissions = permissions;
    }
}
