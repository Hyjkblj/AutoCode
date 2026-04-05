package com.autocode.protocol.model;

import java.util.ArrayList;
import java.util.List;

/**
 * Describes one input parameter in a {@link ToolManifest}.
 */
public class ToolParamSpec {
    private String name;
    /**
     * Suggested values: string | number | integer | boolean | object | array.
     */
    private String type;
    private boolean required;
    private String description;
    private Object defaultValue;
    private List<String> enumValues = new ArrayList<>();

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public String getType() {
        return type;
    }

    public void setType(String type) {
        this.type = type;
    }

    public boolean isRequired() {
        return required;
    }

    public void setRequired(boolean required) {
        this.required = required;
    }

    public String getDescription() {
        return description;
    }

    public void setDescription(String description) {
        this.description = description;
    }

    public Object getDefaultValue() {
        return defaultValue;
    }

    public void setDefaultValue(Object defaultValue) {
        this.defaultValue = defaultValue;
    }

    public List<String> getEnumValues() {
        return enumValues;
    }

    public void setEnumValues(List<String> enumValues) {
        this.enumValues = enumValues;
    }
}
