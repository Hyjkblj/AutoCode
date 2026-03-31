package com.autocode.controlplane.api;

import com.autocode.controlplane.persistence.entity.AuditLogEntity;
import com.autocode.controlplane.persistence.repo.AuditLogRepository;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/api/v1/audits")
public class AuditController {
    private final AuditLogRepository auditLogRepository;

    public AuditController(AuditLogRepository auditLogRepository) {
        this.auditLogRepository = auditLogRepository;
    }

    @GetMapping("/export")
    @PreAuthorize("@projectAuthz.canAccessTask(#taskId)")
    public ResponseEntity<ApiResponse<Map<String, Object>>> exportByTask(@RequestParam("taskId") String taskId) {
        List<AuditLogEntity> logs = auditLogRepository.findByTaskIdOrderByCreatedAtAscAuditIdAsc(taskId);
        List<Map<String, Object>> items = logs.stream().map(l -> Map.<String, Object>of(
                "auditId", l.getAuditId(),
                "taskId", l.getTaskId(),
                "actor", l.getActor(),
                "action", l.getAction(),
                "createdAt", l.getCreatedAt(),
                "prevHash", l.getPrevHash(),
                "entryHash", l.getEntryHash(),
                "detailsJson", l.getDetailsJson()
        )).collect(Collectors.toList());

        boolean chainValid = true;
        String prev = null;
        for (AuditLogEntity log : logs) {
            if (prev != null && log.getPrevHash() != null && !prev.equals(log.getPrevHash())) {
                chainValid = false;
                break;
            }
            prev = log.getEntryHash();
        }

        return ResponseEntity.ok(ApiResponse.ok(Map.of(
                "taskId", taskId,
                "count", items.size(),
                "chainValid", chainValid,
                "items", items
        )));
    }
}

