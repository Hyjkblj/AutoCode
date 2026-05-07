/**
 * Unit tests for TaskService - idempotency and lease management.
 * Validates Requirement 6.4 (comprehensive test coverage for all core services).
 */
package com.autocode.controlplane.service;

import com.autocode.controlplane.api.CreateTaskRequest;
import com.autocode.controlplane.persistence.entity.ApprovalEntity;
import com.autocode.controlplane.persistence.entity.IdempotencyRecordEntity;
import com.autocode.controlplane.persistence.entity.TaskEntity;
import com.autocode.controlplane.persistence.entity.TaskEventEntity;
import com.autocode.controlplane.persistence.repo.ApprovalEntityRepository;
import com.autocode.controlplane.persistence.repo.IdempotencyRecordRepository;
import com.autocode.controlplane.persistence.repo.TaskEntityRepository;
import com.autocode.controlplane.persistence.repo.TaskEventEntityRepository;
import com.autocode.controlplane.service.audit.AuditService;
import com.autocode.controlplane.service.mapper.ModelMapper;
import com.autocode.controlplane.service.observability.ControlPlaneMetrics;
import com.autocode.controlplane.service.protocol.TaskEventValidator;
import com.autocode.controlplane.service.queue.TaskQueuePort;
import com.autocode.controlplane.service.ws.TaskEventPublisher;
import com.autocode.protocol.model.EventType;
import com.autocode.protocol.model.TaskEvent;
import com.autocode.protocol.model.TaskStatus;
import com.autocode.protocol.model.TaskSummary;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.messaging.simp.SimpMessagingTemplate;

import java.time.Instant;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class TaskServiceTest {

    @Mock
    private TaskEntityRepository taskRepository;

    @Mock
    private TaskEventEntityRepository taskEventRepository;

    @Mock
    private ApprovalEntityRepository approvalRepository;

    @Mock
    private IdempotencyRecordRepository idempotencyRecordRepository;

    @Mock
    private TaskQueuePort taskQueue;

    @Mock
    private SimpMessagingTemplate messagingTemplate;

    @Mock
    private ModelMapper modelMapper;

    @Mock
    private ObjectMapper objectMapper;

    @Mock
    private AuditService auditService;

    @Mock
    private TaskEventValidator taskEventValidator;

    private ControlPlaneMetrics metrics;

    @Mock
    private TaskEventPublisher taskEventPublisher;

    private TaskService taskService;

    @BeforeEach
    void setUp() {
        metrics = new ControlPlaneMetrics(new SimpleMeterRegistry());

        taskService = new TaskService(
                taskRepository,
                taskEventRepository,
                approvalRepository,
                idempotencyRecordRepository,
                taskQueue,
                messagingTemplate,
                modelMapper,
                objectMapper,
                auditService,
                taskEventValidator,
                metrics,
                taskEventPublisher,
                60L, // leaseSeconds
                "db", // schedulerMode
                5L // retryBaseBackoffSeconds
        );
    }

    // ========== Idempotency Tests ==========

    @Test
    void createTask_WithoutIdempotencyKey_CreatesNewTask() {
        // Arrange
        CreateTaskRequest request = new CreateTaskRequest();
        request.setProjectId("proj_123");
        request.setPrompt("Test prompt");
        request.setAssistant("coder");
        request.setInputMode("text");
        request.setRiskPolicy("low");
        request.setWorkspacePath("/workspace");

        TaskEntity savedTask = new TaskEntity();
        savedTask.setTaskId("tsk_abc123");
        savedTask.setStatus(TaskStatus.QUEUED);

        TaskSummary expectedSummary = new TaskSummary();
        expectedSummary.setTaskId("tsk_abc123");

        when(taskRepository.saveAndFlush(any(TaskEntity.class))).thenReturn(savedTask);
        when(modelMapper.toSummary(any(TaskEntity.class))).thenReturn(expectedSummary);

        // Act
        TaskSummary result = taskService.createTask(request, null);

        // Assert
        assertNotNull(result);
        assertEquals("tsk_abc123", result.getTaskId());
        verify(taskRepository).saveAndFlush(any(TaskEntity.class));
        verify(taskQueue).enqueue(anyString());
        verify(auditService).log(anyString(), eq("operator"), eq("task.create"), any());
        verify(idempotencyRecordRepository, never()).save(any());
    }

    @Test
    void createTask_WithIdempotencyKey_FirstTime_CreatesTask() {
        // Arrange
        CreateTaskRequest request = new CreateTaskRequest();
        request.setProjectId("proj_123");
        request.setPrompt("Test prompt");
        request.setAssistant("coder");
        request.setInputMode("text");
        request.setRiskPolicy("low");
        request.setWorkspacePath("/workspace");

        String idempotencyKey = "idem_key_123";

        TaskEntity savedTask = new TaskEntity();
        savedTask.setTaskId("tsk_abc123");
        savedTask.setStatus(TaskStatus.QUEUED);

        TaskSummary expectedSummary = new TaskSummary();
        expectedSummary.setTaskId("tsk_abc123");

        when(idempotencyRecordRepository.findById(idempotencyKey)).thenReturn(Optional.empty());
        when(taskRepository.saveAndFlush(any(TaskEntity.class))).thenReturn(savedTask);
        when(modelMapper.toSummary(any(TaskEntity.class))).thenReturn(expectedSummary);

        // Act
        TaskSummary result = taskService.createTask(request, idempotencyKey);

        // Assert
        assertNotNull(result);
        assertEquals("tsk_abc123", result.getTaskId());
        verify(idempotencyRecordRepository).findById(idempotencyKey);
        verify(taskRepository).saveAndFlush(any(TaskEntity.class));
        verify(idempotencyRecordRepository).save(any(IdempotencyRecordEntity.class));
        verify(taskQueue).enqueue(anyString());
    }

    @Test
    void createTask_WithIdempotencyKey_Duplicate_ReturnsExistingTask() {
        // Arrange
        CreateTaskRequest request = new CreateTaskRequest();
        request.setProjectId("proj_123");
        request.setPrompt("Test prompt");
        request.setAssistant("coder");
        request.setInputMode("text");
        request.setRiskPolicy("low");
        request.setWorkspacePath("/workspace");

        String idempotencyKey = "idem_key_123";
        String existingTaskId = "tsk_existing";

        IdempotencyRecordEntity existingRecord = new IdempotencyRecordEntity();
        existingRecord.setIdempotencyKey(idempotencyKey);
        existingRecord.setTaskId(existingTaskId);

        TaskEntity existingTask = new TaskEntity();
        existingTask.setTaskId(existingTaskId);
        existingTask.setStatus(TaskStatus.QUEUED);

        TaskSummary expectedSummary = new TaskSummary();
        expectedSummary.setTaskId(existingTaskId);

        when(idempotencyRecordRepository.findById(idempotencyKey)).thenReturn(Optional.of(existingRecord));
        when(taskRepository.findById(existingTaskId)).thenReturn(Optional.of(existingTask));
        when(modelMapper.toSummary(existingTask)).thenReturn(expectedSummary);

        // Act
        TaskSummary result = taskService.createTask(request, idempotencyKey);

        // Assert
        assertNotNull(result);
        assertEquals(existingTaskId, result.getTaskId());
        verify(idempotencyRecordRepository).findById(idempotencyKey);
        verify(taskRepository, never()).saveAndFlush(any());
        verify(taskQueue, never()).enqueue(anyString());
    }

    @Test
    void createTask_WithIdempotencyKey_ConcurrentRace_HandlesGracefully() {
        // Arrange
        CreateTaskRequest request = new CreateTaskRequest();
        request.setProjectId("proj_123");
        request.setPrompt("Test prompt");
        request.setAssistant("coder");
        request.setInputMode("text");
        request.setRiskPolicy("low");
        request.setWorkspacePath("/workspace");

        String idempotencyKey = "idem_key_123";
        String taskId = "tsk_abc123";

        IdempotencyRecordEntity record = new IdempotencyRecordEntity();
        record.setIdempotencyKey(idempotencyKey);
        record.setTaskId(taskId);

        TaskEntity task = new TaskEntity();
        task.setTaskId(taskId);

        TaskSummary expectedSummary = new TaskSummary();
        expectedSummary.setTaskId(taskId);

        lenient().when(idempotencyRecordRepository.findById(idempotencyKey)).thenReturn(Optional.empty());
        when(taskRepository.saveAndFlush(any(TaskEntity.class))).thenReturn(task);
        when(idempotencyRecordRepository.save(any(IdempotencyRecordEntity.class)))
                .thenThrow(new DataIntegrityViolationException("Duplicate key"));
        lenient().when(idempotencyRecordRepository.findById(idempotencyKey)).thenReturn(Optional.of(record));
        when(taskRepository.findById(taskId)).thenReturn(Optional.of(task));
        when(modelMapper.toSummary(task)).thenReturn(expectedSummary);

        // Act
        TaskSummary result = taskService.createTask(request, idempotencyKey);

        // Assert
        assertNotNull(result);
        assertEquals(taskId, result.getTaskId());
    }

    // ========== Task Retrieval Tests ==========

    @Test
    void getTaskSummary_ExistingTask_ReturnsTask() {
        // Arrange
        String taskId = "tsk_123";
        TaskEntity task = new TaskEntity();
        task.setTaskId(taskId);
        task.setStatus(TaskStatus.RUNNING);

        TaskSummary expectedSummary = new TaskSummary();
        expectedSummary.setTaskId(taskId);

        when(taskRepository.findById(taskId)).thenReturn(Optional.of(task));
        when(modelMapper.toSummary(task)).thenReturn(expectedSummary);

        // Act
        Optional<TaskSummary> result = taskService.getTaskSummary(taskId);

        // Assert
        assertTrue(result.isPresent());
        assertEquals(taskId, result.get().getTaskId());
        verify(taskRepository).findById(taskId);
    }

    @Test
    void getTaskSummary_NonExistentTask_ReturnsEmpty() {
        // Arrange
        String taskId = "tsk_nonexistent";
        when(taskRepository.findById(taskId)).thenReturn(Optional.empty());

        // Act
        Optional<TaskSummary> result = taskService.getTaskSummary(taskId);

        // Assert
        assertFalse(result.isPresent());
        verify(taskRepository).findById(taskId);
    }

    @Test
    void taskExists_ExistingTask_ReturnsTrue() {
        // Arrange
        String taskId = "tsk_123";
        when(taskRepository.existsById(taskId)).thenReturn(true);

        // Act
        boolean result = taskService.taskExists(taskId);

        // Assert
        assertTrue(result);
        verify(taskRepository).existsById(taskId);
    }

    @Test
    void taskExists_NonExistentTask_ReturnsFalse() {
        // Arrange
        String taskId = "tsk_nonexistent";
        when(taskRepository.existsById(taskId)).thenReturn(false);

        // Act
        boolean result = taskService.taskExists(taskId);

        // Assert
        assertFalse(result);
        verify(taskRepository).existsById(taskId);
    }

    // ========== Task Cancellation Tests ==========

    @Test
    void cancelTask_ExistingRunningTask_CancelsSuccessfully() {
        // Arrange
        String taskId = "tsk_123";
        TaskEntity task = new TaskEntity();
        task.setTaskId(taskId);
        task.setStatus(TaskStatus.RUNNING);

        TaskSummary expectedSummary = new TaskSummary();
        expectedSummary.setTaskId(taskId);
        expectedSummary.setStatus(TaskStatus.CANCELED);

        when(taskRepository.findById(taskId)).thenReturn(Optional.of(task));
        when(modelMapper.toSummary(task)).thenReturn(expectedSummary);

        // Act
        Optional<TaskSummary> result = taskService.cancelTask(taskId, "user_cancel");

        // Assert
        assertTrue(result.isPresent());
        assertEquals(TaskStatus.CANCELED, task.getStatus());
        verify(taskRepository, atLeastOnce()).save(task);
        verify(auditService).log(eq(taskId), eq("operator"), eq("task.cancel"), any());
    }

    @Test
    void cancelTask_AlreadyTerminalTask_ReturnsExistingState() {
        // Arrange
        String taskId = "tsk_123";
        TaskEntity task = new TaskEntity();
        task.setTaskId(taskId);
        task.setStatus(TaskStatus.DONE);

        TaskSummary expectedSummary = new TaskSummary();
        expectedSummary.setTaskId(taskId);
        expectedSummary.setStatus(TaskStatus.DONE);

        when(taskRepository.findById(taskId)).thenReturn(Optional.of(task));
        when(modelMapper.toSummary(task)).thenReturn(expectedSummary);

        // Act
        Optional<TaskSummary> result = taskService.cancelTask(taskId, "user_cancel");

        // Assert
        assertTrue(result.isPresent());
        assertEquals(TaskStatus.DONE, result.get().getStatus());
        verify(taskRepository, never()).save(any());
    }

    @Test
    void cancelTask_NonExistentTask_ReturnsEmpty() {
        // Arrange
        String taskId = "tsk_nonexistent";
        when(taskRepository.findById(taskId)).thenReturn(Optional.empty());

        // Act
        Optional<TaskSummary> result = taskService.cancelTask(taskId, "user_cancel");

        // Assert
        assertFalse(result.isPresent());
        verify(taskRepository, never()).save(any());
    }

    // ========== Lease Management Tests ==========

    @Test
    void pollNextTaskForNode_DbMode_NoTasksAvailable_ReturnsEmpty() {
        // Arrange
        String nodeId = "node_123";
        when(taskRepository.findNextEligibleQueuedTaskAt(isNull(), any(Instant.class))).thenReturn(null);
        when(taskRepository.findExpiredRunningLeases(any(Instant.class), eq(50))).thenReturn(java.util.List.of());

        // Act
        Optional<TaskSummary> result = taskService.pollNextTaskForNode(nodeId);

        // Assert
        assertFalse(result.isPresent());
        verify(taskRepository, times(2)).findNextEligibleQueuedTaskAt(isNull(), any(Instant.class));
    }

    @Test
    void pollNextTaskForNode_DbMode_TaskAvailable_ClaimsSuccessfully() {
        // Arrange
        String nodeId = "node_123";
        String taskId = "tsk_abc";

        TaskEntity queuedTask = new TaskEntity();
        queuedTask.setTaskId(taskId);
        queuedTask.setStatus(TaskStatus.QUEUED);

        TaskEntity claimedTask = new TaskEntity();
        claimedTask.setTaskId(taskId);
        claimedTask.setStatus(TaskStatus.RUNNING);
        claimedTask.setAssignedNodeId(nodeId);

        TaskSummary expectedSummary = new TaskSummary();
        expectedSummary.setTaskId(taskId);

        when(taskRepository.findNextEligibleQueuedTaskAt(isNull(), any(Instant.class))).thenReturn(queuedTask);
        when(taskRepository.claimQueuedTask(eq(taskId), eq(nodeId), any(Instant.class), any(Instant.class))).thenReturn(1);
        when(taskRepository.findById(taskId)).thenReturn(Optional.of(claimedTask));
        when(modelMapper.toSummary(claimedTask)).thenReturn(expectedSummary);

        // Act
        Optional<TaskSummary> result = taskService.pollNextTaskForNode(nodeId);

        // Assert
        assertTrue(result.isPresent());
        assertEquals(taskId, result.get().getTaskId());
        verify(taskRepository).claimQueuedTask(eq(taskId), eq(nodeId), any(Instant.class), any(Instant.class));
    }

    @Test
    void pollNextTaskForNode_DbMode_ClaimFails_RetriesNextTask() {
        // Arrange
        String nodeId = "node_123";
        String taskId1 = "tsk_abc";
        String taskId2 = "tsk_def";

        TaskEntity queuedTask1 = new TaskEntity();
        queuedTask1.setTaskId(taskId1);
        queuedTask1.setStatus(TaskStatus.QUEUED);

        TaskEntity queuedTask2 = new TaskEntity();
        queuedTask2.setTaskId(taskId2);
        queuedTask2.setStatus(TaskStatus.QUEUED);

        TaskEntity claimedTask2 = new TaskEntity();
        claimedTask2.setTaskId(taskId2);
        claimedTask2.setStatus(TaskStatus.RUNNING);

        TaskSummary expectedSummary = new TaskSummary();
        expectedSummary.setTaskId(taskId2);

        when(taskRepository.findNextEligibleQueuedTaskAt(isNull(), any(Instant.class)))
                .thenReturn(queuedTask1)
                .thenReturn(queuedTask2);
        when(taskRepository.claimQueuedTask(eq(taskId1), eq(nodeId), any(Instant.class), any(Instant.class))).thenReturn(0);
        when(taskRepository.claimQueuedTask(eq(taskId2), eq(nodeId), any(Instant.class), any(Instant.class))).thenReturn(1);
        when(taskRepository.findById(taskId2)).thenReturn(Optional.of(claimedTask2));
        when(modelMapper.toSummary(claimedTask2)).thenReturn(expectedSummary);

        // Act
        Optional<TaskSummary> result = taskService.pollNextTaskForNode(nodeId);

        // Assert
        assertTrue(result.isPresent());
        assertEquals(taskId2, result.get().getTaskId());
        verify(taskRepository, times(2)).findNextEligibleQueuedTaskAt(isNull(), any(Instant.class));
    }

    @Test
    void pollNextTaskForNode_WithProfile_MatchingTask_ClaimsSuccessfully() {
        // Arrange
        String nodeId = "node_123";
        String profile = "coder";
        String taskId = "tsk_abc";

        TaskEntity queuedTask = new TaskEntity();
        queuedTask.setTaskId(taskId);
        queuedTask.setStatus(TaskStatus.QUEUED);
        queuedTask.setAgentProfile("coder");

        TaskEntity claimedTask = new TaskEntity();
        claimedTask.setTaskId(taskId);
        claimedTask.setStatus(TaskStatus.RUNNING);

        TaskSummary expectedSummary = new TaskSummary();
        expectedSummary.setTaskId(taskId);

        when(taskRepository.findNextEligibleQueuedTaskAt(eq(profile), any(Instant.class))).thenReturn(queuedTask);
        when(taskRepository.claimQueuedTask(eq(taskId), eq(nodeId), any(Instant.class), any(Instant.class))).thenReturn(1);
        when(taskRepository.findById(taskId)).thenReturn(Optional.of(claimedTask));
        when(modelMapper.toSummary(claimedTask)).thenReturn(expectedSummary);

        // Act
        Optional<TaskSummary> result = taskService.pollNextTaskForNode(nodeId, profile);

        // Assert
        assertTrue(result.isPresent());
        assertEquals(taskId, result.get().getTaskId());
        verify(taskRepository).findNextEligibleQueuedTaskAt(eq(profile), any(Instant.class));
    }

    // ========== Approval Tests ==========

    @Test
    void getApprovalDecision_TaskWithApproval_ReturnsDecision() {
        // Arrange
        String taskId = "tsk_123";
        String approvalId = "appr_456";

        TaskEntity task = new TaskEntity();
        task.setTaskId(taskId);
        task.setApprovalId(approvalId);

        ApprovalEntity approval = new ApprovalEntity();
        approval.setApprovalId(approvalId);
        approval.setDecision(com.autocode.protocol.model.ApprovalDecision.APPROVE);

        when(taskRepository.findById(taskId)).thenReturn(Optional.of(task));
        when(approvalRepository.findById(approvalId)).thenReturn(Optional.of(approval));

        // Act
        Optional<com.autocode.protocol.model.ApprovalDecision> result = taskService.getApprovalDecision(taskId);

        // Assert
        assertTrue(result.isPresent());
        assertEquals(com.autocode.protocol.model.ApprovalDecision.APPROVE, result.get());
    }

    @Test
    void getApprovalDecision_TaskWithoutApproval_ReturnsEmpty() {
        // Arrange
        String taskId = "tsk_123";

        TaskEntity task = new TaskEntity();
        task.setTaskId(taskId);
        task.setApprovalId(null);

        when(taskRepository.findById(taskId)).thenReturn(Optional.of(task));

        // Act
        Optional<com.autocode.protocol.model.ApprovalDecision> result = taskService.getApprovalDecision(taskId);

        // Assert
        assertFalse(result.isPresent());
        verify(approvalRepository, never()).findById(any());
    }

    @Test
    void getApprovalDecision_NonExistentTask_ReturnsEmpty() {
        // Arrange
        String taskId = "tsk_nonexistent";
        when(taskRepository.findById(taskId)).thenReturn(Optional.empty());

        // Act
        Optional<com.autocode.protocol.model.ApprovalDecision> result = taskService.getApprovalDecision(taskId);

        // Assert
        assertFalse(result.isPresent());
    }

    // ========== State Machine Validation Tests ==========

    @Test
    void ingestAgentEvent_TerminalState_RejectsTaskDone() {
        String taskId = "tsk_terminal";
        TaskEntity task = new TaskEntity();
        task.setTaskId(taskId);
        task.setStatus(TaskStatus.DONE);
        task.setNextSeq(1L);

        TaskEvent event = new TaskEvent();
        event.setEventId("evt_1");
        event.setType(EventType.TASK_DONE);
        event.setAssistant("coder");

        doNothing().when(taskEventValidator).validateOrThrow(event);
        when(taskRepository.findOptionalByIdForUpdate(taskId)).thenReturn(Optional.of(task));

        // Illegal state transition should throw
        assertThrows(IllegalStateException.class, () ->
                taskService.ingestAgentEvent(taskId, event, null));
    }

    @Test
    void ingestAgentEvent_TerminalState_RejectsTaskFailed() {
        String taskId = "tsk_failed";
        TaskEntity task = new TaskEntity();
        task.setTaskId(taskId);
        task.setStatus(TaskStatus.FAILED);
        task.setNextSeq(1L);

        TaskEvent event = new TaskEvent();
        event.setEventId("evt_2");
        event.setType(EventType.TASK_FAILED);
        event.setAssistant("coder");
        event.setPayload(java.util.Map.of("reason", "test_failure"));

        doNothing().when(taskEventValidator).validateOrThrow(event);
        when(taskRepository.findOptionalByIdForUpdate(taskId)).thenReturn(Optional.of(task));

        // Illegal state transition should throw
        assertThrows(IllegalStateException.class, () ->
                taskService.ingestAgentEvent(taskId, event, null));
    }

    @Test
    void ingestAgentEvent_QueuedState_RejectsTaskDone() {
        String taskId = "tsk_queued";
        TaskEntity task = new TaskEntity();
        task.setTaskId(taskId);
        task.setStatus(TaskStatus.QUEUED);
        task.setNextSeq(1L);

        TaskEvent event = new TaskEvent();
        event.setEventId("evt_3");
        event.setType(EventType.TASK_DONE);
        event.setAssistant("coder");

        doNothing().when(taskEventValidator).validateOrThrow(event);
        when(taskRepository.findOptionalByIdForUpdate(taskId)).thenReturn(Optional.of(task));

        // TASK_DONE is only legal from RUNNING, not QUEUED — should throw
        assertThrows(IllegalStateException.class, () ->
                taskService.ingestAgentEvent(taskId, event, null));
    }

    @Test
    void ingestAgentEvent_RunningState_AcceptsTaskDone() {
        String taskId = "tsk_running";
        TaskEntity task = new TaskEntity();
        task.setTaskId(taskId);
        task.setStatus(TaskStatus.RUNNING);
        task.setNextSeq(1L);
        task.setAssistant("coder");
        task.setSessionId("ses_1");

        TaskEvent event = new TaskEvent();
        event.setEventId("evt_4");
        event.setType(EventType.TASK_DONE);
        event.setAssistant("coder");

        TaskSummary summary = new TaskSummary();
        summary.setTaskId(taskId);

        doNothing().when(taskEventValidator).validateOrThrow(event);
        when(taskRepository.findOptionalByIdForUpdate(taskId)).thenReturn(Optional.of(task));
        when(taskEventRepository.existsById("evt_4")).thenReturn(false);
        when(taskEventRepository.save(any(TaskEventEntity.class))).thenReturn(null);
        when(modelMapper.toSummary(task)).thenReturn(summary);

        Optional<TaskService.IngestResult> result = taskService.ingestAgentEvent(taskId, event, null);

        assertTrue(result.isPresent());
        assertFalse(result.get().duplicate());
        assertEquals(TaskStatus.DONE, task.getStatus());
    }

    @Test
    void ingestAgentEvent_TerminalState_AllowsHeartbeat() {
        String taskId = "tsk_heartbeat";
        TaskEntity task = new TaskEntity();
        task.setTaskId(taskId);
        task.setStatus(TaskStatus.DONE);
        task.setNextSeq(1L);
        task.setAssistant("coder");
        task.setSessionId("ses_1");

        TaskEvent event = new TaskEvent();
        event.setEventId("evt_5");
        event.setType(EventType.HEARTBEAT);
        event.setAssistant("coder");

        TaskSummary summary = new TaskSummary();
        summary.setTaskId(taskId);

        doNothing().when(taskEventValidator).validateOrThrow(event);
        when(taskRepository.findOptionalByIdForUpdate(taskId)).thenReturn(Optional.of(task));
        when(taskEventRepository.existsById("evt_5")).thenReturn(false);
        when(taskEventRepository.save(any(TaskEventEntity.class))).thenReturn(null);
        when(modelMapper.toSummary(task)).thenReturn(summary);

        Optional<TaskService.IngestResult> result = taskService.ingestAgentEvent(taskId, event, null);

        // Heartbeat should be accepted even in terminal state
        assertTrue(result.isPresent());
    }
}
