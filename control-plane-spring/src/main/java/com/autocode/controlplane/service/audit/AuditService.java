/**
 * Writes structured audit records for operator/agent actions.
 */
package com.autocode.controlplane.service.audit;

import com.autocode.controlplane.persistence.entity.AuditLogEntity;
import com.autocode.controlplane.persistence.repo.AuditLogRepository;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
public class AuditService {
    private final AuditLogRepository auditLogRepository;
    private final ObjectMapper objectMapper;

    public AuditService(AuditLogRepository auditLogRepository, ObjectMapper objectMapper) {
        this.auditLogRepository = auditLogRepository;
        this.objectMapper = objectMapper;
    }

    @Transactional
    public void log(String taskId, String actor, String action, Map<String, Object> details) {
        AuditLogEntity log = new AuditLogEntity();
        log.setAuditId("aud_" + UUID.randomUUID().toString().replace("-", ""));
        log.setTaskId(taskId);
        log.setActor(actor);
        log.setAction(action);
        log.setCreatedAt(Instant.now());
        log.setDetailsJson(toJson(details));
        String prevHash = null;
        if (taskId != null && !taskId.isBlank()) {
            AuditLogEntity latest = auditLogRepository.findLatestForTask(taskId);
            if (latest != null) {
                prevHash = latest.getEntryHash();
            }
        }
        log.setPrevHash(prevHash);
        log.setEntryHash(computeEntryHash(log));
        auditLogRepository.save(log);
    }

    public List<AuditLogEntity> latestByTask(String taskId) {
        return auditLogRepository.findTop50ByTaskIdOrderByCreatedAtDesc(taskId);
    }

    private String toJson(Map<String, Object> details) {
        try {
            return objectMapper.writeValueAsString(details == null ? Map.of() : details);
        } catch (JsonProcessingException ex) {
            throw new IllegalStateException("failed to serialize audit details", ex);
        }
    }

    private String computeEntryHash(AuditLogEntity log) {
        String material = String.join("|",
                safe(log.getPrevHash()),
                safe(log.getAuditId()),
                safe(log.getTaskId()),
                safe(log.getActor()),
                safe(log.getAction()),
                safeInstant(log.getCreatedAt()),
                safe(log.getDetailsJson())
        );
        return sha256Hex(material);
    }

    private static String safe(String s) {
        return s == null ? "" : s;
    }

    private static String safeInstant(Instant i) {
        return i == null ? "" : i.toString();
    }

    private static String sha256Hex(String s) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] out = digest.digest(s.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder(out.length * 2);
            for (byte b : out) {
                sb.append(String.format("%02x", b));
            }
            return sb.toString();
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 not available", e);
        }
    }
}
