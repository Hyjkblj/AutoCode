package com.autocode.protocol.validation;

import com.autocode.protocol.model.ServiceRuntimeDescriptor;
import com.autocode.protocol.model.ServiceRuntimeDescriptor.EnvVarSpec;
import com.autocode.protocol.model.ServiceRuntimeDescriptor.HealthCheckSpec;
import com.autocode.protocol.model.ServiceRuntimeDescriptor.PortBinding;
import com.autocode.protocol.model.ServiceRuntimeDescriptor.StartupDescriptor;

import java.util.List;

/**
 * Lightweight validation for {@link ServiceRuntimeDescriptor} (v1).
 */
public final class ServiceRuntimeDescriptorContractValidator {
    private ServiceRuntimeDescriptorContractValidator() {}

    public static void validate(ServiceRuntimeDescriptor d) {
        if (d == null) {
            throw new ContractViolationException("ServiceRuntimeDescriptor must not be null");
        }
        if (d.getSchemaVersion() != 1) {
            throw new ContractViolationException("Unsupported ServiceRuntimeDescriptor.schemaVersion: " + d.getSchemaVersion());
        }
        if (isBlank(d.getServiceId())) {
            throw new ContractViolationException("ServiceRuntimeDescriptor.serviceId is required");
        }
        List<PortBinding> ports = d.getPorts();
        if (ports != null) {
            for (PortBinding p : ports) {
                if (p == null) {
                    throw new ContractViolationException("ports entries must not be null");
                }
                int port = p.getPort();
                if (port < 1 || port > 65535) {
                    throw new ContractViolationException("ports[].port must be between 1 and 65535");
                }
            }
        }
        HealthCheckSpec hc = d.getHealthCheck();
        if (hc != null) {
            if (isBlank(hc.getPath())) {
                throw new ContractViolationException("healthCheck.path is required when healthCheck is present");
            }
        }
        List<EnvVarSpec> env = d.getEnvironment();
        if (env != null) {
            for (EnvVarSpec e : env) {
                if (e == null) {
                    throw new ContractViolationException("environment entries must not be null");
                }
                if (isBlank(e.getName())) {
                    throw new ContractViolationException("environment[].name is required");
                }
            }
        }
        StartupDescriptor su = d.getStartup();
        if (su != null) {
            if (isBlank(su.getCommand())) {
                throw new ContractViolationException("startup.command is required when startup is present");
            }
        }
    }

    private static boolean isBlank(String s) {
        return s == null || s.trim().isEmpty();
    }
}
