/**
 * Aggregated artifacts response for a task (patch previews and audit logs).
 */
package com.autocode.controlplane.api;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

public class TaskArtifactsResponse {
    private String taskId;
    private List<Map<String, Object>> patchPreviews = new ArrayList<>();
    private List<Map<String, Object>> auditLogs = new ArrayList<>();

    public String getTaskId() {
        return taskId;
    }

    public void setTaskId(String taskId) {
        this.taskId = taskId;
    }

    public List<Map<String, Object>> getPatchPreviews() {
        return patchPreviews;
    }

    public void setPatchPreviews(List<Map<String, Object>> patchPreviews) {
        this.patchPreviews = patchPreviews;
    }

    public List<Map<String, Object>> getAuditLogs() {
        return auditLogs;
    }

    public void setAuditLogs(List<Map<String, Object>> auditLogs) {
        this.auditLogs = auditLogs;
    }
}
