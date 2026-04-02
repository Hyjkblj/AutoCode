package com.autocode.protocol.model;

import java.util.List;

/**
 * Describes how a backend service is exposed, probed, configured, and started locally.
 * Schema: {@code schema/runtime/v1/service_runtime_descriptor.v1.schema.json}.
 */
public class ServiceRuntimeDescriptor {
    private int schemaVersion = 1;
    private String serviceId;
    private String displayName;
    private List<PortBinding> ports;
    private HealthCheckSpec healthCheck;
    private List<EnvVarSpec> environment;
    private StartupDescriptor startup;

    public int getSchemaVersion() {
        return schemaVersion;
    }

    public void setSchemaVersion(int schemaVersion) {
        this.schemaVersion = schemaVersion;
    }

    public String getServiceId() {
        return serviceId;
    }

    public void setServiceId(String serviceId) {
        this.serviceId = serviceId;
    }

    public String getDisplayName() {
        return displayName;
    }

    public void setDisplayName(String displayName) {
        this.displayName = displayName;
    }

    public List<PortBinding> getPorts() {
        return ports;
    }

    public void setPorts(List<PortBinding> ports) {
        this.ports = ports;
    }

    public HealthCheckSpec getHealthCheck() {
        return healthCheck;
    }

    public void setHealthCheck(HealthCheckSpec healthCheck) {
        this.healthCheck = healthCheck;
    }

    public List<EnvVarSpec> getEnvironment() {
        return environment;
    }

    public void setEnvironment(List<EnvVarSpec> environment) {
        this.environment = environment;
    }

    public StartupDescriptor getStartup() {
        return startup;
    }

    public void setStartup(StartupDescriptor startup) {
        this.startup = startup;
    }

    public static class PortBinding {
        private String name;
        private int port;
        private String protocol;

        public String getName() {
            return name;
        }

        public void setName(String name) {
            this.name = name;
        }

        public int getPort() {
            return port;
        }

        public void setPort(int port) {
            this.port = port;
        }

        public String getProtocol() {
            return protocol;
        }

        public void setProtocol(String protocol) {
            this.protocol = protocol;
        }
    }

    public static class HealthCheckSpec {
        private String path;
        private String method;
        private String portName;

        public String getPath() {
            return path;
        }

        public void setPath(String path) {
            this.path = path;
        }

        public String getMethod() {
            return method;
        }

        public void setMethod(String method) {
            this.method = method;
        }

        public String getPortName() {
            return portName;
        }

        public void setPortName(String portName) {
            this.portName = portName;
        }
    }

    public static class EnvVarSpec {
        private String name;
        private String description;
        private Boolean required;
        private String defaultValue;

        public String getName() {
            return name;
        }

        public void setName(String name) {
            this.name = name;
        }

        public String getDescription() {
            return description;
        }

        public void setDescription(String description) {
            this.description = description;
        }

        public Boolean getRequired() {
            return required;
        }

        public void setRequired(Boolean required) {
            this.required = required;
        }

        public String getDefaultValue() {
            return defaultValue;
        }

        public void setDefaultValue(String defaultValue) {
            this.defaultValue = defaultValue;
        }
    }

    public static class StartupDescriptor {
        private String command;
        private String workingDir;
        private List<String> args;

        public String getCommand() {
            return command;
        }

        public void setCommand(String command) {
            this.command = command;
        }

        public String getWorkingDir() {
            return workingDir;
        }

        public void setWorkingDir(String workingDir) {
            this.workingDir = workingDir;
        }

        public List<String> getArgs() {
            return args;
        }

        public void setArgs(List<String> args) {
            this.args = args;
        }
    }
}
