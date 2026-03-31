package com.autocode.controlplane.artifacts.ports;

import java.util.Map;

public interface AuditPort {
    void append(String taskId, String actor, String action, Map<String, Object> details);
}

