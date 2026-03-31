/**
 * Aggregates derived artifacts (patch previews, audit logs) from persisted events for UI consumption.
 */
package com.autocode.controlplane.service;

import com.autocode.controlplane.api.TaskArtifactsResponse;
import com.autocode.controlplane.persistence.entity.AuditLogEntity;
import com.autocode.controlplane.persistence.entity.TaskEventEntity;
import com.autocode.controlplane.persistence.repo.AuditLogRepository;
import com.autocode.controlplane.persistence.repo.TaskEventEntityRepository;
import com.autocode.protocol.model.EventType;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Service
@Transactional(readOnly = true)
public class ArtifactQueryService {
    private final TaskEventEntityRepository taskEventRepository;
    private final AuditLogRepository auditLogRepository;
    private final ObjectMapper objectMapper;

    public ArtifactQueryService(
            TaskEventEntityRepository taskEventRepository,
            AuditLogRepository auditLogRepository,
            ObjectMapper objectMapper
    ) {
        this.taskEventRepository = taskEventRepository;
        this.auditLogRepository = auditLogRepository;
        this.objectMapper = objectMapper;
    }

    public TaskArtifactsResponse getArtifacts(String taskId) {
        TaskArtifactsResponse response = new TaskArtifactsResponse();
        response.setTaskId(taskId);

        List<TaskEventEntity> events = taskEventRepository.findByTaskIdOrderBySeqNumAsc(taskId);
        List<Map<String, Object>> patches = new ArrayList<>();
        for (TaskEventEntity event : events) {
            if (event.getEventType() == EventType.FILE_PATCH_PREVIEW) {
                Map<String, Object> payload = parseJsonMap(event.getPayloadJson());
                payload.put("seq", event.getSeqNum());
                payload.put("timestamp", event.getEventTimestamp());
                patches.add(payload);
            }
        }
        response.setPatchPreviews(patches);

        List<AuditLogEntity> audits = auditLogRepository.findTop50ByTaskIdOrderByCreatedAtDesc(taskId);
        List<Map<String, Object>> auditMaps = new ArrayList<>();
        for (AuditLogEntity log : audits) {
            Map<String, Object> item = new HashMap<>();
            item.put("auditId", log.getAuditId());
            item.put("actor", log.getActor());
            item.put("action", log.getAction());
            item.put("createdAt", log.getCreatedAt());
            item.put("prevHash", log.getPrevHash());
            item.put("entryHash", log.getEntryHash());
            item.put("details", parseJsonMap(log.getDetailsJson()));
            auditMaps.add(item);
        }
        response.setAuditLogs(auditMaps);

        return response;
    }

    private Map<String, Object> parseJsonMap(String json) {
        if (json == null || json.isBlank()) {
            return new HashMap<>();
        }
        try {
            return objectMapper.readValue(json, new TypeReference<>() {
            });
        } catch (JsonProcessingException ex) {
            Map<String, Object> fallback = new HashMap<>();
            fallback.put("raw", json);
            return fallback;
        }
    }
}
