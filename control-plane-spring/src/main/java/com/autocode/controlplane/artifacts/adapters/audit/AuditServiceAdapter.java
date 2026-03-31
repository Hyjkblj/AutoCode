package com.autocode.controlplane.artifacts.adapters.audit;

import com.autocode.controlplane.artifacts.ports.AuditPort;
import com.autocode.controlplane.service.audit.AuditService;
import org.springframework.stereotype.Component;

import java.util.Map;

@Component
public class AuditServiceAdapter implements AuditPort {
    private final AuditService auditService;

    public AuditServiceAdapter(AuditService auditService) {
        this.auditService = auditService;
    }

    @Override
    public void append(String taskId, String actor, String action, Map<String, Object> details) {
        auditService.log(taskId, actor, action, details);
    }
}

