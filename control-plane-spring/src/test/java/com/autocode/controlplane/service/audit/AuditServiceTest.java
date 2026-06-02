/**
 * Unit tests for AuditService - compliance trail generation.
 * Validates Requirement 6.4 (comprehensive test coverage for all core services).
 */
package com.autocode.controlplane.service.audit;

import com.autocode.controlplane.persistence.entity.AuditLogEntity;
import com.autocode.controlplane.persistence.repo.AuditLogRepository;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.Instant;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class AuditServiceTest {

    @Mock
    private AuditLogRepository auditLogRepository;

    @Mock
    private ObjectMapper objectMapper;

    private AuditService auditService;

    @BeforeEach
    void setUp() {
        auditService = new AuditService(auditLogRepository, objectMapper);
    }

    // ========== Log Creation Tests ==========

    @Test
    void log_ValidInput_CreatesAuditLog() throws JsonProcessingException {
        // Arrange
        String taskId = "tsk_123";
        String actor = "user@example.com";
        String action = "task.create";
        Map<String, Object> details = Map.of("projectId", "proj_456", "assistant", "coder");

        when(objectMapper.writeValueAsString(details)).thenReturn("{\"projectId\":\"proj_456\",\"assistant\":\"coder\"}");
        when(auditLogRepository.findLatestForTask(taskId)).thenReturn(null);

        ArgumentCaptor<AuditLogEntity> captor = ArgumentCaptor.forClass(AuditLogEntity.class);

        // Act
        auditService.log(taskId, actor, action, details);

        // Assert
        verify(auditLogRepository).save(captor.capture());
        AuditLogEntity savedLog = captor.getValue();

        assertNotNull(savedLog);
        assertTrue(savedLog.getAuditId().startsWith("aud_"));
        assertEquals(taskId, savedLog.getTaskId());
        assertEquals(actor, savedLog.getActor());
        assertEquals(action, savedLog.getAction());
        assertNotNull(savedLog.getCreatedAt());
        assertNotNull(savedLog.getDetailsJson());
        assertNull(savedLog.getPrevHash()); // First log has no previous hash
        assertNotNull(savedLog.getEntryHash());
    }

    @Test
    void log_WithPreviousLog_ChainsHashCorrectly() throws JsonProcessingException {
        // Arrange
        String taskId = "tsk_123";
        String actor = "user@example.com";
        String action = "task.update";
        Map<String, Object> details = Map.of("status", "running");

        AuditLogEntity previousLog = new AuditLogEntity();
        previousLog.setAuditId("aud_previous");
        previousLog.setEntryHash("previous_hash_value");

        when(objectMapper.writeValueAsString(details)).thenReturn("{\"status\":\"running\"}");
        when(auditLogRepository.findLatestForTask(taskId)).thenReturn(previousLog);

        ArgumentCaptor<AuditLogEntity> captor = ArgumentCaptor.forClass(AuditLogEntity.class);

        // Act
        auditService.log(taskId, actor, action, details);

        // Assert
        verify(auditLogRepository).save(captor.capture());
        AuditLogEntity savedLog = captor.getValue();

        assertNotNull(savedLog);
        assertEquals("previous_hash_value", savedLog.getPrevHash());
        assertNotNull(savedLog.getEntryHash());
        assertNotEquals(savedLog.getPrevHash(), savedLog.getEntryHash());
    }

    @Test
    void log_NullDetails_HandlesGracefully() throws JsonProcessingException {
        // Arrange
        String taskId = "tsk_123";
        String actor = "system";
        String action = "task.heartbeat";

        when(objectMapper.writeValueAsString(Map.of())).thenReturn("{}");
        when(auditLogRepository.findLatestForTask(taskId)).thenReturn(null);

        ArgumentCaptor<AuditLogEntity> captor = ArgumentCaptor.forClass(AuditLogEntity.class);

        // Act
        auditService.log(taskId, actor, action, null);

        // Assert
        verify(auditLogRepository).save(captor.capture());
        AuditLogEntity savedLog = captor.getValue();

        assertNotNull(savedLog);
        assertEquals(taskId, savedLog.getTaskId());
        assertEquals(actor, savedLog.getActor());
        assertEquals(action, savedLog.getAction());
        verify(objectMapper).writeValueAsString(Map.of());
    }

    @Test
    void log_EmptyDetails_HandlesGracefully() throws JsonProcessingException {
        // Arrange
        String taskId = "tsk_123";
        String actor = "system";
        String action = "task.ping";
        Map<String, Object> details = Map.of();

        when(objectMapper.writeValueAsString(details)).thenReturn("{}");
        when(auditLogRepository.findLatestForTask(taskId)).thenReturn(null);

        ArgumentCaptor<AuditLogEntity> captor = ArgumentCaptor.forClass(AuditLogEntity.class);

        // Act
        auditService.log(taskId, actor, action, details);

        // Assert
        verify(auditLogRepository).save(captor.capture());
        AuditLogEntity savedLog = captor.getValue();

        assertNotNull(savedLog);
        assertNotNull(savedLog.getDetailsJson());
    }

    @Test
    void log_NullTaskId_CreatesLogWithoutChaining() throws JsonProcessingException {
        // Arrange
        String actor = "system";
        String action = "system.startup";
        Map<String, Object> details = Map.of("version", "2.0");

        when(objectMapper.writeValueAsString(details)).thenReturn("{\"version\":\"2.0\"}");

        ArgumentCaptor<AuditLogEntity> captor = ArgumentCaptor.forClass(AuditLogEntity.class);

        // Act
        auditService.log(null, actor, action, details);

        // Assert
        verify(auditLogRepository).save(captor.capture());
        verify(auditLogRepository, never()).findLatestForTask(any());

        AuditLogEntity savedLog = captor.getValue();
        assertNotNull(savedLog);
        assertNull(savedLog.getTaskId());
        assertNull(savedLog.getPrevHash());
        assertNotNull(savedLog.getEntryHash());
    }

    @Test
    void log_BlankTaskId_CreatesLogWithoutChaining() throws JsonProcessingException {
        // Arrange
        String actor = "system";
        String action = "system.config";
        Map<String, Object> details = Map.of("setting", "value");

        when(objectMapper.writeValueAsString(details)).thenReturn("{\"setting\":\"value\"}");

        ArgumentCaptor<AuditLogEntity> captor = ArgumentCaptor.forClass(AuditLogEntity.class);

        // Act
        auditService.log("  ", actor, action, details);

        // Assert
        verify(auditLogRepository).save(captor.capture());
        verify(auditLogRepository, never()).findLatestForTask(any());

        AuditLogEntity savedLog = captor.getValue();
        assertNotNull(savedLog);
        assertNull(savedLog.getPrevHash());
    }

    @Test
    void log_JsonSerializationFailure_ThrowsException() throws JsonProcessingException {
        // Arrange
        String taskId = "tsk_123";
        String actor = "user@example.com";
        String action = "task.create";
        Map<String, Object> details = Map.of("key", "value");

        when(objectMapper.writeValueAsString(details))
                .thenThrow(new JsonProcessingException("Serialization error") {});

        // Act & Assert
        assertThrows(IllegalStateException.class, () ->
                auditService.log(taskId, actor, action, details)
        );
        verify(auditLogRepository, never()).save(any());
    }

    @Test
    void log_ComplexDetails_SerializesCorrectly() throws JsonProcessingException {
        // Arrange
        String taskId = "tsk_123";
        String actor = "operator";
        String action = "approval.decide";
        Map<String, Object> details = Map.of(
                "approvalId", "appr_789",
                "decision", "approve",
                "comment", "Looks good",
                "metadata", Map.of("reviewer", "senior_dev", "timestamp", "2024-01-01T00:00:00Z")
        );

        String expectedJson = "{\"approvalId\":\"appr_789\",\"decision\":\"approve\",\"comment\":\"Looks good\",\"metadata\":{\"reviewer\":\"senior_dev\",\"timestamp\":\"2024-01-01T00:00:00Z\"}}";
        when(objectMapper.writeValueAsString(details)).thenReturn(expectedJson);
        when(auditLogRepository.findLatestForTask(taskId)).thenReturn(null);

        ArgumentCaptor<AuditLogEntity> captor = ArgumentCaptor.forClass(AuditLogEntity.class);

        // Act
        auditService.log(taskId, actor, action, details);

        // Assert
        verify(auditLogRepository).save(captor.capture());
        AuditLogEntity savedLog = captor.getValue();

        assertNotNull(savedLog);
        assertEquals(expectedJson, savedLog.getDetailsJson());
    }

    // ========== Hash Chain Tests ==========

    @Test
    void log_MultipleSequentialLogs_CreatesValidChain() throws JsonProcessingException {
        // Arrange
        String taskId = "tsk_123";

        when(objectMapper.writeValueAsString(any())).thenReturn("{}");

        AuditLogEntity log1 = new AuditLogEntity();
        log1.setAuditId("aud_1");
        log1.setEntryHash("hash_1");

        AuditLogEntity log2 = new AuditLogEntity();
        log2.setAuditId("aud_2");
        log2.setEntryHash("hash_2");

        when(auditLogRepository.findLatestForTask(taskId))
                .thenReturn(null)
                .thenReturn(log1)
                .thenReturn(log2);

        ArgumentCaptor<AuditLogEntity> captor = ArgumentCaptor.forClass(AuditLogEntity.class);

        // Act
        auditService.log(taskId, "actor1", "action1", Map.of());
        auditService.log(taskId, "actor2", "action2", Map.of());
        auditService.log(taskId, "actor3", "action3", Map.of());

        // Assert
        verify(auditLogRepository, times(3)).save(captor.capture());
        List<AuditLogEntity> savedLogs = captor.getAllValues();

        // First log has no previous hash
        assertNull(savedLogs.get(0).getPrevHash());

        // Second log chains to first
        assertEquals("hash_1", savedLogs.get(1).getPrevHash());

        // Third log chains to second
        assertEquals("hash_2", savedLogs.get(2).getPrevHash());
    }

    @Test
    void log_DifferentTasks_MaintainsSeparateChains() throws JsonProcessingException {
        // Arrange
        String taskId1 = "tsk_123";
        String taskId2 = "tsk_456";

        when(objectMapper.writeValueAsString(any())).thenReturn("{}");

        AuditLogEntity log1Task1 = new AuditLogEntity();
        log1Task1.setAuditId("aud_1_1");
        log1Task1.setEntryHash("hash_1_1");

        AuditLogEntity log1Task2 = new AuditLogEntity();
        log1Task2.setAuditId("aud_2_1");
        log1Task2.setEntryHash("hash_2_1");

        when(auditLogRepository.findLatestForTask(taskId1))
                .thenReturn(null)
                .thenReturn(log1Task1);
        when(auditLogRepository.findLatestForTask(taskId2))
                .thenReturn(null)
                .thenReturn(log1Task2);

        ArgumentCaptor<AuditLogEntity> captor = ArgumentCaptor.forClass(AuditLogEntity.class);

        // Act
        auditService.log(taskId1, "actor", "action1", Map.of());
        auditService.log(taskId2, "actor", "action2", Map.of());
        auditService.log(taskId1, "actor", "action3", Map.of());
        auditService.log(taskId2, "actor", "action4", Map.of());

        // Assert
        verify(auditLogRepository, times(4)).save(captor.capture());
        List<AuditLogEntity> savedLogs = captor.getAllValues();

        // Task 1 chain
        assertNull(savedLogs.get(0).getPrevHash());
        assertEquals("hash_1_1", savedLogs.get(2).getPrevHash());

        // Task 2 chain
        assertNull(savedLogs.get(1).getPrevHash());
        assertEquals("hash_2_1", savedLogs.get(3).getPrevHash());
    }

    // ========== Retrieval Tests ==========

    @Test
    void latestByTask_ExistingLogs_ReturnsOrderedList() {
        // Arrange
        String taskId = "tsk_123";
        List<AuditLogEntity> expectedLogs = List.of(
                createAuditLog("aud_3", taskId, "action3", Instant.now()),
                createAuditLog("aud_2", taskId, "action2", Instant.now().minusSeconds(60)),
                createAuditLog("aud_1", taskId, "action1", Instant.now().minusSeconds(120))
        );

        when(auditLogRepository.findTop50ByTaskIdOrderByCreatedAtDesc(taskId)).thenReturn(expectedLogs);

        // Act
        List<AuditLogEntity> result = auditService.latestByTask(taskId);

        // Assert
        assertNotNull(result);
        assertEquals(3, result.size());
        assertEquals("aud_3", result.get(0).getAuditId());
        assertEquals("aud_2", result.get(1).getAuditId());
        assertEquals("aud_1", result.get(2).getAuditId());
        verify(auditLogRepository).findTop50ByTaskIdOrderByCreatedAtDesc(taskId);
    }

    @Test
    void latestByTask_NoLogs_ReturnsEmptyList() {
        // Arrange
        String taskId = "tsk_empty";
        when(auditLogRepository.findTop50ByTaskIdOrderByCreatedAtDesc(taskId)).thenReturn(List.of());

        // Act
        List<AuditLogEntity> result = auditService.latestByTask(taskId);

        // Assert
        assertNotNull(result);
        assertTrue(result.isEmpty());
        verify(auditLogRepository).findTop50ByTaskIdOrderByCreatedAtDesc(taskId);
    }

    @Test
    void latestByTask_MaxLimit_Returns50Logs() {
        // Arrange
        String taskId = "tsk_123";
        List<AuditLogEntity> manyLogs = new java.util.ArrayList<>();
        for (int i = 0; i < 50; i++) {
            manyLogs.add(createAuditLog("aud_" + i, taskId, "action" + i, Instant.now().minusSeconds(i)));
        }

        when(auditLogRepository.findTop50ByTaskIdOrderByCreatedAtDesc(taskId)).thenReturn(manyLogs);

        // Act
        List<AuditLogEntity> result = auditService.latestByTask(taskId);

        // Assert
        assertNotNull(result);
        assertEquals(50, result.size());
    }

    // ========== Helper Methods ==========

    private AuditLogEntity createAuditLog(String auditId, String taskId, String action, Instant createdAt) {
        AuditLogEntity log = new AuditLogEntity();
        log.setAuditId(auditId);
        log.setTaskId(taskId);
        log.setActor("test_actor");
        log.setAction(action);
        log.setCreatedAt(createdAt);
        log.setDetailsJson("{}");
        log.setEntryHash("hash_" + auditId);
        return log;
    }
}
