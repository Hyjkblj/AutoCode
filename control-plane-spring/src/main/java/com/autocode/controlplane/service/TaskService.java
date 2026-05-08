/**
 * Core task orchestration: create/poll/ingest events, drive status transitions, and broadcast updates.
 */
package com.autocode.controlplane.service;

import com.autocode.controlplane.api.ApprovalDecisionRequest;
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
import com.autocode.controlplane.service.protocol.TaskStateMachine;
import com.autocode.controlplane.service.queue.TaskQueuePort;
import com.autocode.controlplane.service.queue.TaskQueueMessage;
import com.autocode.controlplane.service.ws.TaskEventPublisher;
import com.autocode.protocol.model.ApprovalDecision;
import com.autocode.protocol.model.EventType;
import com.autocode.protocol.model.TaskEvent;
import com.autocode.protocol.model.TaskStatus;
import com.autocode.protocol.model.TaskSummary;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.data.domain.PageRequest;

import java.time.Instant;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

@Service
@Transactional
public class TaskService {
    private final TaskEntityRepository taskRepository;
    private final TaskEventEntityRepository taskEventRepository;
    private final ApprovalEntityRepository approvalRepository;
    private final IdempotencyRecordRepository idempotencyRecordRepository;
    private final TaskQueuePort taskQueue;
    private final SimpMessagingTemplate messagingTemplate;
    private final ModelMapper modelMapper;
    private final ObjectMapper objectMapper;
    private final AuditService auditService;
    private final TaskEventValidator taskEventValidator;
    private final TaskStateMachine stateMachine;
    private final ControlPlaneMetrics metrics;
    private final TaskEventPublisher taskEventPublisher;
    private final long leaseSeconds;
    private final String schedulerMode;
    private final long retryBaseBackoffSeconds;

    public TaskService(
            TaskEntityRepository taskRepository,
            TaskEventEntityRepository taskEventRepository,
            ApprovalEntityRepository approvalRepository,
            IdempotencyRecordRepository idempotencyRecordRepository,
            TaskQueuePort taskQueue,
            SimpMessagingTemplate messagingTemplate,
            ModelMapper modelMapper,
            ObjectMapper objectMapper,
            AuditService auditService,
            TaskEventValidator taskEventValidator,
            TaskStateMachine stateMachine,
            ControlPlaneMetrics metrics,
            TaskEventPublisher taskEventPublisher,
            @Value("${mvp.queue.lease-seconds:60}") long leaseSeconds,
            @Value("${mvp.scheduler.mode:db}") String schedulerMode,
            @Value("${mvp.scheduler.retry.base-backoff-seconds:5}") long retryBaseBackoffSeconds
    ) {
        this.taskRepository = taskRepository;
        this.taskEventRepository = taskEventRepository;
        this.approvalRepository = approvalRepository;
        this.idempotencyRecordRepository = idempotencyRecordRepository;
        this.taskQueue = taskQueue;
        this.messagingTemplate = messagingTemplate;
        this.modelMapper = modelMapper;
        this.objectMapper = objectMapper;
        this.auditService = auditService;
        this.taskEventValidator = taskEventValidator;
        this.stateMachine = stateMachine;
        this.metrics = metrics;
        this.taskEventPublisher = taskEventPublisher;
        this.leaseSeconds = leaseSeconds;
        this.schedulerMode = schedulerMode == null ? "db" : schedulerMode.trim().toLowerCase();
        this.retryBaseBackoffSeconds = Math.max(1, retryBaseBackoffSeconds);
    }

    /**
     * 创建任务：支持幂等键、落库、入队，并写入一条 TASK_CREATED 系统事件。
     */
    @Transactional(propagation = Propagation.NOT_SUPPORTED)
    public TaskSummary createTask(CreateTaskRequest request, String idempotencyKey) {
        String normalizedIdem = normalizeIdempotencyKey(idempotencyKey);
        if (normalizedIdem != null) {
            Optional<IdempotencyRecordEntity> record = idempotencyRecordRepository.findById(normalizedIdem);
            if (record.isPresent()) {
                return taskRepository.findById(record.get().getTaskId())
                        .map(modelMapper::toSummary)
                        .orElseThrow(() -> new IllegalStateException("idempotency mapping points to missing task"));
            }
        }

        Instant now = Instant.now();
        TaskEntity task = new TaskEntity();
        if (normalizedIdem != null) {
            // Deterministic taskId prevents concurrent duplicates for the same idempotency key within a project.
            task.setTaskId("tsk_" + sha256Hex(normalizedIdem + "|" + request.getProjectId()).substring(0, 32));
        } else {
            task.setTaskId("tsk_" + randomId());
        }
        task.setSessionId("ses_" + randomId());
        task.setProjectId(request.getProjectId());
        task.setPrompt(request.getPrompt());
        task.setAssistant(request.getAssistant().toLowerCase());
        task.setInputMode(request.getInputMode());
        task.setRiskPolicy(request.getRiskPolicy());
        task.setWorkspacePath(request.getWorkspacePath());
        task.setAgentProfile(request.getAgentProfile() == null || request.getAgentProfile().isBlank()
                ? "coder"
                : request.getAgentProfile().trim().toLowerCase());
        task.setSessionKey(request.getSessionKey());
        task.setStatus(TaskStatus.QUEUED);
        task.setCreatedAt(now);
        task.setUpdatedAt(now);
        task.setNextSeq(1L);
        task.setApprovalDecision(ApprovalDecision.PENDING);

        try {
            taskRepository.saveAndFlush(task);
        } catch (DataIntegrityViolationException ex) {
            // Another request with the same deterministic idempotency-derived taskId may have won the race.
            if (normalizedIdem != null) {
                return taskRepository.findById(task.getTaskId())
                        .map(modelMapper::toSummary)
                        .orElseThrow(() -> ex);
            }
            throw ex;
        }
        // 入队：让 Agent 通过轮询“领取任务”并开始执行
        taskQueue.enqueue(task.getTaskId());

        if (normalizedIdem != null) {
            IdempotencyRecordEntity record = new IdempotencyRecordEntity();
            record.setIdempotencyKey(normalizedIdem);
            record.setTaskId(task.getTaskId());
            record.setCreatedAt(now);
            try {
                idempotencyRecordRepository.save(record);
            } catch (DataIntegrityViolationException ex) {
                // Concurrent insert: return the already-mapped task deterministically.
                return idempotencyRecordRepository.findById(normalizedIdem)
                        .flatMap(r -> taskRepository.findById(r.getTaskId()))
                        .map(modelMapper::toSummary)
                        .orElseThrow(() -> ex);
            }
        }

        pushSystemEvent(task, EventType.TASK_CREATED, Map.of(
                "projectId", task.getProjectId(),
                "assistant", task.getAssistant(),
                "riskPolicy", task.getRiskPolicy()
        ));
        auditService.log(task.getTaskId(), "operator", "task.create", Map.of(
                "projectId", task.getProjectId(),
                "assistant", task.getAssistant(),
                "riskPolicy", task.getRiskPolicy()
        ));
        metrics.tasksCreated.increment();

        return modelMapper.toSummary(task);
    }

    private String normalizeIdempotencyKey(String key) {
        if (key == null) return null;
        String k = key.trim();
        return k.isBlank() ? null : k;
    }

    private String sha256Hex(String s) {
        try {
            java.security.MessageDigest digest = java.security.MessageDigest.getInstance("SHA-256");
            byte[] out = digest.digest(s.getBytes(java.nio.charset.StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder(out.length * 2);
            for (byte b : out) {
                sb.append(String.format("%02x", b));
            }
            return sb.toString();
        } catch (java.security.NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 not available", e);
        }
    }

    /**
     * 查询任务摘要（用于任务列表/详情页展示）。
     */
    @Transactional(readOnly = true)
    public Optional<TaskSummary> getTaskSummary(String taskId) {
        return taskRepository.findById(taskId).map(task -> {
            if (task.getStatus() != TaskStatus.FAILED) {
                return modelMapper.toSummary(task);
            }
            Map<String, Object> latestFailurePayload = taskEventRepository
                    .findTopByTaskIdAndEventTypeOrderBySeqNumDesc(taskId, EventType.TASK_FAILED)
                    .map(TaskEventEntity::getPayloadJson)
                    .map(this::readPayload)
                    .orElseGet(HashMap::new);
            String failureReason = asNonBlankString(latestFailurePayload.get("reason"), null);
            String failureErrorCode = asNonBlankString(latestFailurePayload.get("errorCode"), null);
            return modelMapper.toSummary(task, failureReason, failureErrorCode);
        });
    }

    /**
     * Lists recent task summaries under a project (optionally filtered by assistant).
     */
    @Transactional(readOnly = true)
    public List<TaskSummary> listTaskSummaries(String projectId, String assistant) {
        String normalizedProjectId = projectId == null ? "" : projectId.trim();
        if (normalizedProjectId.isEmpty()) {
            return List.of();
        }
        String normalizedAssistant = assistant == null ? null : assistant.trim().toLowerCase(Locale.ROOT);
        if (normalizedAssistant != null && normalizedAssistant.isEmpty()) {
            normalizedAssistant = null;
        }
        return taskRepository
                .findRecentByProjectAndAssistant(normalizedProjectId, normalizedAssistant, PageRequest.of(0, 200))
                .stream()
                .map(modelMapper::toSummary)
                .toList();
    }

    @Transactional(readOnly = true)
    public boolean taskExists(String taskId) {
        return taskRepository.existsById(taskId);
    }

    /**
     * 查询任务事件历史（支持按 seq 增量拉取；参数名 lastEventId 实际对应 lastSeq）。
     */
    @Transactional(readOnly = true)
    public List<TaskEvent> getTaskEvents(String taskId, Long lastSeq) {
        List<TaskEventEntity> events = lastSeq == null
                ? taskEventRepository.findByTaskIdOrderBySeqNumAsc(taskId)
                : taskEventRepository.findTop200ByTaskIdAndSeqNumGreaterThanOrderBySeqNumAsc(taskId, lastSeq);
        return events.stream().map(this::toProtocolEvent).toList();
    }

    /**
     * 取消任务：写入 CANCELED 状态，并追加一条 TASK_FAILED(reason=user_cancel) 事件用于回放。
     */
    public Optional<TaskSummary> cancelTask(String taskId, String reason) {
        Optional<TaskEntity> taskOptional = taskRepository.findById(taskId);
        if (taskOptional.isEmpty()) {
            return Optional.empty();
        }

        TaskEntity task = taskOptional.get();
        if (isTerminal(task.getStatus())) {
            return Optional.of(modelMapper.toSummary(task));
        }

        task.setStatus(TaskStatus.CANCELED);
        task.setUpdatedAt(Instant.now());
        taskRepository.save(task);
        pushSystemEvent(task, EventType.TASK_FAILED, Map.of("reason", reason == null ? "user_cancel" : reason));
        auditService.log(task.getTaskId(), "operator", "task.cancel", Map.of("reason", reason == null ? "user_cancel" : reason));
        return Optional.of(modelMapper.toSummary(task));
    }

    /**
     * 操作者审批：更新 approvals 与任务状态，并追加 APPROVAL_RESULT 系统事件。
     */
    public Optional<TaskSummary> applyApproval(String taskId, ApprovalDecisionRequest request) {
        Optional<TaskEntity> taskOptional = taskRepository.findById(taskId);
        Optional<ApprovalEntity> approvalOptional = approvalRepository.findById(request.getApprovalId());
        if (taskOptional.isEmpty() || approvalOptional.isEmpty()) {
            return Optional.empty();
        }

        TaskEntity task = taskOptional.get();
        ApprovalEntity approval = approvalOptional.get();
        if (!taskId.equals(approval.getTaskId())) {
            return Optional.empty();
        }
        if (isTerminal(task.getStatus())) {
            return Optional.of(modelMapper.toSummary(task));
        }

        ApprovalDecision decision = parseDecision(request.getDecision());
        approval.setDecision(decision);
        approval.setCommentText(request.getComment());
        approval.setDecidedAt(Instant.now());
        approvalRepository.save(approval);

        task.setApprovalDecision(decision);
        task.setUpdatedAt(approval.getDecidedAt());
        if (decision == ApprovalDecision.APPROVE) {
            task.setStatus(TaskStatus.RUNNING);
        } else if (decision == ApprovalDecision.REJECT) {
            task.setStatus(TaskStatus.CANCELED);
        }
        taskRepository.save(task);

        Map<String, Object> payload = new HashMap<>();
        payload.put("approvalId", approval.getApprovalId());
        payload.put("decision", decision.name().toLowerCase());
        payload.put("comment", request.getComment());
        pushSystemEvent(task, EventType.APPROVAL_RESULT, payload);
        auditService.log(task.getTaskId(), "operator", "approval.decide", Map.of(
                "approvalId", approval.getApprovalId(),
                "decision", decision.name().toLowerCase(),
                "comment", request.getComment() == null ? "" : request.getComment()
        ));

        return Optional.of(modelMapper.toSummary(task));
    }

    /**
     * Agent 领取下一条任务：从队列取 taskId，校验仍为 QUEUED 后“占用”并置为 RUNNING。
     */
    public Optional<TaskSummary> pollNextTaskForNode(String nodeId) {
        return pollNextTaskForNode(nodeId, null);
    }

    public Optional<TaskSummary> pollNextTaskForNode(String nodeId, String profile) {
        var sample = metrics.startPollSample();
        if ("db".equals(schedulerMode)) {
            try {
                return pollNextTaskForNodeDb(nodeId, profile);
            } finally {
                sample.stop(metrics.pollDuration);
            }
        }
        boolean attemptedRecovery = false;
        while (true) {
            // 出队：队列为空则返回 204（若存在过期租约，可触发一次回收再重试）
            TaskQueueMessage msg = taskQueue.pollMessage();
            if (msg == null || msg.taskId() == null) {
                if (!attemptedRecovery) {
                    attemptedRecovery = true;
                    recoverExpiredLeasesToQueue();
                    continue;
                }
                return Optional.empty();
            }
            String taskId = msg.taskId();

            Optional<TaskEntity> taskOptional = taskRepository.findById(taskId);
            if (taskOptional.isEmpty()) {
                taskQueue.ack(msg.receipt());
                continue;
            }
            TaskEntity task = taskOptional.get();
            if (task.getStatus() != TaskStatus.QUEUED) {
                // 处理“跑着跑着 agent 掉线”的场景：若队列里出现 RUNNING 且 lease 已过期的任务，立即回收并重新入队
                if (task.getStatus() == TaskStatus.RUNNING
                        && task.getLeaseExpiresAt() != null
                        && task.getLeaseExpiresAt().isBefore(Instant.now())) {
                    int updated = taskRepository.requeueIfLeaseExpired(task.getTaskId(), Instant.now());
                    if (updated > 0) {
                        taskQueue.enqueue(task.getTaskId());
                        auditService.log(task.getTaskId(), "control-plane", "task.lease.requeue", Map.of(
                                "reason", "lease_expired_on_poll"
                        ));
                    }
                }
                taskQueue.ack(msg.receipt());
                continue;
            }

            // Profile routing: if agent declares profile, only claim matching tasks; otherwise accept any.
            if (profile != null && !profile.isBlank()) {
                String p = profile.trim().toLowerCase();
                String required = task.getAgentProfile() == null ? "coder" : task.getAgentProfile().trim().toLowerCase();
                if (!p.equals(required)) {
                    taskQueue.nack(msg.receipt(), true);
                    continue;
                }
            }

            // Lane serialization: if sessionKey is set and there is a RUNNING task with same key, defer.
            if (task.getSessionKey() != null && !task.getSessionKey().isBlank()
                    && taskRepository.existsRunningBySessionKey(task.getSessionKey())) {
                taskQueue.nack(msg.receipt(), true);
                continue;
            }

            // 任务被该节点“领取/占用”：使用 DB 原子 claim，避免并发重复领取
            Instant now = Instant.now();
            Instant expiresAt = now.plusSeconds(Math.max(5, leaseSeconds));
            int claimed = taskRepository.claimQueuedTask(task.getTaskId(), nodeId, now, expiresAt);
            if (claimed == 0) {
                taskQueue.nack(msg.receipt(), true);
                continue;
            }
            taskQueue.ack(msg.receipt());
            task = taskRepository.findById(task.getTaskId()).orElseThrow();
            pushSystemEvent(task, EventType.TASK_STARTED, Map.of("nodeId", nodeId));
            metrics.tasksPolled.increment();
            sample.stop(metrics.pollDuration);
            return Optional.of(modelMapper.toSummary(task));
        }
    }

    private Optional<TaskSummary> pollNextTaskForNodeDb(String nodeId, String profile) {
        boolean attemptedRecovery = false;
        String p = profile == null ? null : profile.trim().toLowerCase();
        while (true) {
            TaskEntity next = taskRepository.findNextEligibleQueuedTaskAt(p, Instant.now());
            if (next == null) {
                if (!attemptedRecovery) {
                    attemptedRecovery = true;
                    recoverExpiredLeasesToQueue();
                    continue;
                }
                return Optional.empty();
            }
            Instant now = Instant.now();
            Instant expiresAt = now.plusSeconds(Math.max(5, leaseSeconds));
            int claimed = taskRepository.claimQueuedTask(next.getTaskId(), nodeId, now, expiresAt);
            if (claimed == 0) {
                continue;
            }
            TaskEntity task = taskRepository.findById(next.getTaskId()).orElseThrow();
            pushSystemEvent(task, EventType.TASK_STARTED, Map.of("nodeId", nodeId));
            metrics.tasksPolled.increment();
            return Optional.of(modelMapper.toSummary(task));
        }
    }

    /**
     * Periodic lease recovery so expired RUNNING tasks are re-queued even when the queue is not empty.
     * This keeps lease semantics stable without relying on "queue empty" triggers.
     */
    @Scheduled(fixedDelayString = "${mvp.scheduler.lease-recover-interval-ms:5000}")
    public void scheduledLeaseRecovery() {
        recoverExpiredLeasesToQueue();
    }

    private void recoverExpiredLeasesToQueue() {
        Instant now = Instant.now();
        List<TaskEntity> expired = taskRepository.findExpiredRunningLeases(now, 50);
        for (TaskEntity task : expired) {
            int updated = taskRepository.requeueIfLeaseExpired(task.getTaskId(), now);
            if (updated > 0) {
                taskQueue.enqueue(task.getTaskId());
                auditService.log(task.getTaskId(), "control-plane", "task.lease.requeue", Map.of(
                        "reason", "lease_expired"
                ));
                metrics.leaseRequeued.increment();
            }
        }
    }

    /**
     * Agent 查询当前任务的审批决策（PENDING/APPROVE/REJECT）。
     */
    @Transactional(readOnly = true)
    public Optional<ApprovalDecision> getApprovalDecision(String taskId) {
        Optional<TaskEntity> taskOptional = taskRepository.findById(taskId);
        if (taskOptional.isEmpty() || taskOptional.get().getApprovalId() == null) {
            return Optional.empty();
        }
        return approvalRepository.findById(taskOptional.get().getApprovalId()).map(ApprovalEntity::getDecision);
    }

    /**
     * Ingest result carrying the task summary, assigned seq, and whether the event was a duplicate.
     */
    public record IngestResult(TaskSummary summary, long assignedSeq, boolean duplicate) {}

    /**
     * 摄取 Agent 上报事件：去重、分配 seq、驱动状态机、落库并通过 WS 广播。
     */
    public Optional<TaskSummary> ingestAgentEvent(String taskId, TaskEvent event) {
        return ingestAgentEvent(taskId, event, null).map(IngestResult::summary);
    }

    public Optional<IngestResult> ingestAgentEvent(String taskId, TaskEvent event, String nodeId) {
        // Lock task row to make seq allocation and status folding stable under concurrent ingest.
        TaskEntity task = taskRepository.findOptionalByIdForUpdate(taskId).orElse(null);
        if (task == null) {
            return Optional.empty();
        }

        validateAssignedNodeForIngest(task, nodeId);
        ensureEventId(event);
        if (taskEventRepository.existsById(event.getEventId())) {
            metrics.duplicateEvents.increment();
            // For duplicates, look up the original seq from the persisted event
            long originalSeq = taskEventRepository.findById(event.getEventId())
                    .map(TaskEventEntity::getSeqNum)
                    .orElse(0L);
            return Optional.of(new IngestResult(modelMapper.toSummary(task), originalSeq, true));
        }

        // 规范化事件（补齐 task/session/assistant/timestamp，并分配 seq）
        normalizeEvent(task, event);
        updateTaskStateFromEvent(task, event);

        // 如果检测到审批上下文漂移，立即追加一条系统失败事件并审计（拒绝把任务标记为 DONE）
        if (Boolean.TRUE.equals(event.getPayload().get("approvalContextMismatch"))) {
            pushSystemEvent(task, EventType.TASK_FAILED, Map.of(
                    "reason", "approval_context_mismatch",
                    "expected", event.getPayload().get("expectedApprovalContext"),
                    "actual", event.getPayload().get("actualApprovalContext")
            ));
            auditService.log(task.getTaskId(), "control-plane", "approval.context.mismatch", Map.of(
                    "expected", event.getPayload().get("expectedApprovalContext"),
                    "actual", event.getPayload().get("actualApprovalContext")
            ));
        }

        taskRepository.save(task);
        saveEvent(event);
        // Broadcast only after transaction commits to avoid "ghost" events.
        taskEventPublisher.publishAfterCommit(task.getTaskId(), event);
        auditService.log(task.getTaskId(), "agent", "event.ingest", Map.of(
                "eventType", event.getType().name(),
                "seq", event.getSeq()
        ));
        metrics.taskEventsIngested.increment();

        return Optional.of(new IngestResult(modelMapper.toSummary(task), event.getSeq(), false));
    }

    private void validateAssignedNodeForIngest(TaskEntity task, String nodeId) {
        String assignedNodeId = task.getAssignedNodeId();
        if (assignedNodeId == null || assignedNodeId.isBlank()) {
            return;
        }
        if (nodeId == null || nodeId.isBlank()) {
            throw new AccessDeniedException("nodeId is required for assigned task");
        }
        if (!assignedNodeId.equals(nodeId)) {
            throw new AccessDeniedException("task not assigned to this node");
        }
    }

    private void ensureEventId(TaskEvent event) {
        if (event.getEventId() == null || event.getEventId().isBlank()) {
            throw new IllegalArgumentException("event.eventId is required");
        }
    }

    private void normalizeEvent(TaskEntity task, TaskEvent event) {
        event.setTaskId(task.getTaskId());
        event.setSessionId(task.getSessionId());
        if (event.getAssistant() == null || event.getAssistant().isBlank()) {
            event.setAssistant(task.getAssistant());
        }
        if (event.getTimestamp() == null) {
            event.setTimestamp(Instant.now());
        }
        if (event.getPayload() == null) {
            event.setPayload(new HashMap<>());
        } else {
            event.setPayload(new HashMap<>(event.getPayload()));
        }
        normalizeReviewPayloadAliases(event.getPayload());
        event.setSeq(task.getNextSeq());
        task.setNextSeq(task.getNextSeq() + 1);
    }

    private void updateTaskStateFromEvent(TaskEntity task, TaskEvent event) {
        task.setUpdatedAt(Instant.now());

        // Validate state transition legality via TaskStateMachine
        TaskStateMachine.TransitionResult transition = stateMachine.validate(task.getStatus(), event.getType());
        if (!transition.isAllowed()) {
            metrics.illegalStateTransitions.increment();
            String auditEvent = stateMachine.isTerminal(task.getStatus())
                    ? "event.rejected.terminal_state"
                    : "event.rejected.illegal_transition";
            auditService.log(task.getTaskId(), "control-plane", auditEvent, Map.of(
                    "eventType", event.getType().name(),
                    "currentStatus", task.getStatus().name(),
                    "reason", transition.rejectionReason()
            ));
            throw new IllegalStateException(transition.rejectionReason());
        }
        if (event.getType() == EventType.APPROVAL_REQUIRED) {
            String approvalId = extractOrCreateApprovalId(event);
            task.setApprovalId(approvalId);
            ApprovalEntity approvalEntity = approvalRepository.findById(approvalId).orElseGet(ApprovalEntity::new);
            approvalEntity.setApprovalId(approvalId);
            approvalEntity.setTaskId(task.getTaskId());
            if (approvalEntity.getDecision() == null) {
                approvalEntity.setDecision(ApprovalDecision.PENDING);
            }
            // 将审批上下文持久化，后续用于校验“审批内容”与“实际执行”一致
            Map<String, Object> context = buildApprovalContext(event.getPayload());
            approvalEntity.setApprovalContextJson(writePayload(context));
            approvalRepository.save(approvalEntity);
            task.setApprovalDecision(approvalEntity.getDecision());
            if (approvalEntity.getDecision() == ApprovalDecision.PENDING) {
                task.setStatus(TaskStatus.WAITING_APPROVAL);
            } else if (approvalEntity.getDecision() == ApprovalDecision.APPROVE) {
                task.setStatus(TaskStatus.RUNNING);
            } else if (approvalEntity.getDecision() == ApprovalDecision.REJECT) {
                task.setStatus(TaskStatus.CANCELED);
            }
            // Bind approval context for audit/UI; the control plane currently does not enforce it,
            // but keeping a stable copy here allows future consistency checks.
            Object ctx = event.getPayload().get("approvalContext");
            if (ctx == null) {
                event.getPayload().put("approvalContext", context);
            }
            event.getPayload().put("approvalId", approvalId);
        } else if (event.getType() == EventType.TOOL_START) {
            // 审批强绑定校验：执行工具启动时，若任务存在 approvalId，则校验 command/cwd 与审批时一致
            Object tool = event.getPayload().get("tool");
            if ("command.exec".equals(tool) && task.getApprovalId() != null && !task.getApprovalId().isBlank()) {
                ApprovalEntity approval = approvalRepository.findById(task.getApprovalId()).orElse(null);
                if (approval != null) {
                    Map<String, Object> expected = readPayload(approval.getApprovalContextJson());
                    Map<String, Object> actual = buildApprovalContext(event.getPayload());
                    if (!expected.isEmpty() && !isApprovalContextEqualForToolStart(expected, actual)) {
                        markFailed(task);
                        event.getPayload().put("approvalContextMismatch", true);
                        event.getPayload().put("expectedApprovalContext", expected);
                        event.getPayload().put("actualApprovalContext", actual);
                    }
                }
            }
        } else if (event.getType() == EventType.DEPLOY_PLAN) {
            if (!authorizeDeployEvent(task, event, true)) {
                return;
            }
            task.setStatus(TaskStatus.RUNNING);
            auditService.log(task.getTaskId(), "agent", "deploy.plan", deployPlanAuditDetails(event.getPayload()));
        } else if (event.getType() == EventType.DEPLOY_RESULT) {
            if (!authorizeDeployEvent(task, event, false)) {
                return;
            }
            applyDeployResultStatus(task, event.getPayload());
            auditService.log(task.getTaskId(), "agent", "deploy.result", deployResultAuditDetails(event.getPayload()));
        } else if (event.getType() == EventType.TASK_DONE) {
            task.setStatus(TaskStatus.DONE);
        } else if (event.getType() == EventType.TASK_FAILED) {
            markFailed(task);
            auditTaskFailureDetails(task, event);
        }
        auditReviewResultIfPresent(task, event);
    }

    private void normalizeReviewPayloadAliases(Map<String, Object> payload) {
        if (payload == null) {
            return;
        }
        String riskLevel = asNonBlankString(payload.get("riskLevel"), null);
        String legacyRiskLevel = asNonBlankString(payload.get("risk_level"), null);
        if (riskLevel == null && legacyRiskLevel != null) {
            payload.put("riskLevel", legacyRiskLevel);
        }
        if (legacyRiskLevel == null && riskLevel != null) {
            payload.put("risk_level", riskLevel);
        }
    }

    private void auditReviewResultIfPresent(TaskEntity task, TaskEvent event) {
        if (event.getType() != EventType.ASSISTANT_OUTPUT && event.getType() != EventType.TASK_FAILED) {
            return;
        }
        if (event.getPayload() == null) {
            return;
        }
        String riskLevel = asNonBlankString(firstNonNull(
                event.getPayload().get("riskLevel"),
                event.getPayload().get("risk_level")
        ), null);
        Object issues = event.getPayload().get("issues");
        if (riskLevel == null && !(issues instanceof List<?>)) {
            return;
        }

        Map<String, Object> details = new HashMap<>();
        putIfPresent(details, "riskLevel", riskLevel);
        if (issues instanceof List<?> issueList) {
            details.put("issues", issueList);
        }
        putIfPresent(details, "summary", asNonBlankString(event.getPayload().get("summary"), null));
        details.put("eventType", event.getType().name());
        details.put("seq", event.getSeq());
        auditService.log(task.getTaskId(), "agent", "review.result", details);
    }

    private void auditTaskFailureDetails(TaskEntity task, TaskEvent event) {
        if (event.getPayload() == null) {
            return;
        }
        String reason = asNonBlankString(event.getPayload().get("reason"), null);
        if (reason == null || !"fix_loop_exhausted".equalsIgnoreCase(reason)) {
            return;
        }
        Map<String, Object> details = new HashMap<>();
        details.put("reason", "fix_loop_exhausted");
        putIfPresent(details, "attempt", asInteger(event.getPayload().get("attempt")));
        putIfPresent(details, "maxAttempts", asInteger(event.getPayload().get("maxAttempts")));
        putIfPresent(details, "lastTestError", asNonBlankString(event.getPayload().get("lastTestError"), null));
        details.put("seq", event.getSeq());
        auditService.log(task.getTaskId(), "agent", "fix_loop.exhausted", details);
    }

    private Map<String, Object> buildApprovalContext(Map<String, Object> payload) {
        Map<String, Object> context = new HashMap<>();
        if (payload == null) {
            return context;
        }
        Map<String, Object> nested = extractMap(payload.get("context"));
        Map<String, Object> legacyNested = extractMap(payload.get("approvalContext"));

        context.put("action", firstNonNull(
                payload.get("action"),
                nested.get("action"),
                legacyNested.get("action")
        ));
        context.put("tool", firstNonNull(
                payload.get("tool"),
                nested.get("tool"),
                legacyNested.get("tool")
        ));
        context.put("workspaceRef", firstNonNull(
                payload.get("workspaceRef"),
                nested.get("workspaceRef"),
                legacyNested.get("workspaceRef"),
                payload.get("cwd"),
                legacyNested.get("cwd")
        ));
        context.put("inputsHash", firstNonNull(
                payload.get("inputsHash"),
                nested.get("inputsHash"),
                legacyNested.get("inputsHash")
        ));
        context.put("command", firstNonNull(
                payload.get("command"),
                nested.get("command"),
                legacyNested.get("command")
        ));
        context.put("cwd", firstNonNull(
                payload.get("cwd"),
                nested.get("cwd"),
                legacyNested.get("cwd")
        ));
        return context;
    }

    /**
     * command.exec runtime events don't carry inputsHash, so keep that key optional to avoid false mismatches.
     */
    private boolean isApprovalContextEqualForToolStart(Map<String, Object> expected, Map<String, Object> actual) {
        return contextFieldMatches(expected, actual, "action", true)
                && contextFieldMatches(expected, actual, "tool", true)
                && contextFieldMatches(expected, actual, "workspaceRef", true)
                && contextFieldMatches(expected, actual, "command", true)
                && contextFieldMatches(expected, actual, "cwd", true)
                && contextFieldMatches(expected, actual, "inputsHash", false);
    }

    /**
     * Deploy plan payloads are contracted around context fields; command/cwd are not required there.
     */
    private boolean isApprovalContextEqualForDeployPlan(Map<String, Object> expected, Map<String, Object> actual) {
        return contextFieldMatches(expected, actual, "action", true)
                && contextFieldMatches(expected, actual, "tool", true)
                && contextFieldMatches(expected, actual, "workspaceRef", true)
                && contextFieldMatches(expected, actual, "inputsHash", true);
    }

    /**
     * Deploy events are privileged actions. If a task has an approvalId bound, deploy plan/result
     * must only be accepted after explicit APPROVE, and deploy plan must match approved context.
     */
    private boolean authorizeDeployEvent(TaskEntity task, TaskEvent event, boolean validateContext) {
        if (task.getApprovalId() == null || task.getApprovalId().isBlank()) {
            return true;
        }
        ApprovalEntity approval = approvalRepository.findById(task.getApprovalId()).orElse(null);
        if (approval == null) {
            denyDeploy(task, event, "approval_missing", null);
            markFailed(task);
            return false;
        }

        ApprovalDecision decision = approval.getDecision();
        if (decision != ApprovalDecision.APPROVE) {
            String decisionText = decision == null ? "pending" : decision.name().toLowerCase(Locale.ROOT);
            denyDeploy(task, event, "approval_not_approved", decisionText);
            return false;
        }

        if (validateContext) {
            Map<String, Object> expected = readPayload(approval.getApprovalContextJson());
            Map<String, Object> actual = buildApprovalContext(event.getPayload());
            if (!expected.isEmpty() && !isApprovalContextEqualForDeployPlan(expected, actual)) {
                event.getPayload().put("approvalContextMismatch", true);
                event.getPayload().put("expectedApprovalContext", expected);
                event.getPayload().put("actualApprovalContext", actual);
                denyDeploy(task, event, "approval_context_mismatch", "approve");
                markFailed(task);
                return false;
            }
        }
        return true;
    }

    private void denyDeploy(TaskEntity task, TaskEvent event, String reason, String approvalDecision) {
        Map<String, Object> details = new HashMap<>();
        details.put("reason", reason);
        String requestId = asNonBlankString(event.getPayload().get("requestId"), null);
        putIfPresent(details, "requestId", requestId);
        putIfPresent(details, "approvalDecision", approvalDecision);
        auditService.log(task.getTaskId(), "control-plane", "deploy.authz.denied", details);
    }

    private boolean contextFieldMatches(
            Map<String, Object> expected,
            Map<String, Object> actual,
            String key,
            boolean requiredWhenExpectedPresent
    ) {
        String expectedValue = normalizeContextValue(expected.get(key));
        if (expectedValue == null) {
            return true;
        }
        String actualValue = normalizeContextValue(actual.get(key));
        if (actualValue == null) {
            return !requiredWhenExpectedPresent;
        }
        return expectedValue.equals(actualValue);
    }

    private String normalizeContextValue(Object value) {
        if (value instanceof String s) {
            String trimmed = s.trim();
            return trimmed.isEmpty() ? null : trimmed;
        }
        return value == null ? null : value.toString();
    }

    private boolean safeEquals(Object a, Object b) {
        return a == null ? b == null : a.equals(b);
    }

    private Map<String, Object> extractMap(Object value) {
        if (value instanceof Map<?, ?> map) {
            @SuppressWarnings("unchecked")
            Map<String, Object> cast = (Map<String, Object>) map;
            return cast;
        }
        return Map.of();
    }

    private Object firstNonNull(Object... values) {
        for (Object value : values) {
            if (value != null) {
                return value;
            }
        }
        return null;
    }

    private void applyDeployResultStatus(TaskEntity task, Map<String, Object> payload) {
        if (isTerminal(task.getStatus())) {
            return;
        }
        String status = asNonBlankString(payload == null ? null : payload.get("status"), "")
                .toLowerCase(Locale.ROOT);
        switch (status) {
            case "accepted", "running" -> task.setStatus(TaskStatus.RUNNING);
            case "success" -> task.setStatus(TaskStatus.DONE);
            case "failed" -> markFailed(task);
            case "rejected", "canceled", "cancelled" -> task.setStatus(TaskStatus.CANCELED);
            default -> {
                // Keep existing status for unknown values to avoid accidental regressions.
            }
        }
    }

    private void markFailed(TaskEntity task) {
        task.setStatus(TaskStatus.FAILED);
        // Best-effort: backoff for potential retry orchestration (kept minimal for MVP).
        int nextRetry = Math.min(50, Math.max(0, task.getRetryCount()) + 1);
        task.setRetryCount(nextRetry);
        long delaySeconds = retryBaseBackoffSeconds * (1L << Math.min(6, nextRetry)); // cap growth
        task.setNextRunAt(Instant.now().plusSeconds(delaySeconds));
    }

    private Map<String, Object> deployPlanAuditDetails(Map<String, Object> payload) {
        Map<String, Object> details = new HashMap<>();
        putIfPresent(details, "requestId", asNonBlankString(payload.get("requestId"), null));
        putIfPresent(details, "environment", asNonBlankString(payload.get("environment"), null));
        putIfPresent(details, "strategy", asNonBlankString(payload.get("strategy"), null));
        putIfPresent(details, "triggeredBy", asNonBlankString(payload.get("triggeredBy"), null));

        Map<String, Object> artifact = extractMap(payload.get("artifact"));
        putIfPresent(details, "artifactId", asNonBlankString(artifact.get("artifactId"), null));
        putIfPresent(details, "artifactType", asNonBlankString(artifact.get("type"), null));
        return details;
    }

    private Map<String, Object> deployResultAuditDetails(Map<String, Object> payload) {
        Map<String, Object> details = new HashMap<>();
        putIfPresent(details, "requestId", asNonBlankString(payload.get("requestId"), null));
        putIfPresent(details, "status", asNonBlankString(payload.get("status"), null));
        putIfPresent(details, "environment", asNonBlankString(payload.get("environment"), null));
        putIfPresent(details, "deploymentId", asNonBlankString(payload.get("deploymentId"), null));
        putIfPresent(details, "endpointUrl", asNonBlankString(payload.get("endpointUrl"), null));

        Map<String, Object> resultArtifact = extractMap(payload.get("resultArtifact"));
        putIfPresent(details, "resultArtifactId", asNonBlankString(resultArtifact.get("artifactId"), null));
        return details;
    }

    private void putIfPresent(Map<String, Object> target, String key, Object value) {
        if (value != null) {
            target.put(key, value);
        }
    }

    private String asNonBlankString(Object value, String fallback) {
        if (value instanceof String s && !s.isBlank()) {
            return s;
        }
        return fallback;
    }

    private Integer asInteger(Object value) {
        if (value instanceof Number number) {
            return number.intValue();
        }
        if (value instanceof String text) {
            String trimmed = text.trim();
            if (!trimmed.isEmpty()) {
                try {
                    return Integer.parseInt(trimmed);
                } catch (NumberFormatException ignored) {
                    return null;
                }
            }
        }
        return null;
    }

    private String extractOrCreateApprovalId(TaskEvent event) {
        Object value = event.getPayload().get("approvalId");
        if (value instanceof String id && !id.isBlank()) {
            return id;
        }
        return "apr_" + randomId();
    }

    private void pushSystemEvent(TaskEntity task, EventType type, Map<String, Object> payload) {
        Map<String, Object> safePayload = new HashMap<>(payload);
        // Guard against stale nextSeq values on the task row. This can happen after retries/crashes and
        // previously caused continuous duplicate-key failures on uq_task_events_task_seq.
        for (int attempt = 0; attempt < 2; attempt++) {
            long nextSeq = alignNextSeq(task);

            TaskEvent event = new TaskEvent();
            event.setEventId("evt_" + randomId());
            event.setTaskId(task.getTaskId());
            event.setSessionId(task.getSessionId());
            event.setAssistant(task.getAssistant());
            event.setType(type);
            event.setTimestamp(Instant.now());
            event.setPayload(new HashMap<>(safePayload));
            event.setSeq(nextSeq);
            event.setEventVersion(1);

            task.setNextSeq(nextSeq + 1);
            taskRepository.save(task);
            try {
                saveEvent(event);
                taskEventPublisher.publishAfterCommit(task.getTaskId(), event);
                return;
            } catch (DataIntegrityViolationException ex) {
                if (!isTaskSeqDuplicate(ex) || attempt == 1) {
                    throw ex;
                }
                // Retry once with a refreshed sequence baseline from persisted events.
                task.setNextSeq(nextSeq + 1);
                taskRepository.save(task);
            }
        }
    }

    private long alignNextSeq(TaskEntity task) {
        long fromTask = Math.max(1L, task.getNextSeq());
        long fromEvents = taskEventRepository.findTopByTaskIdOrderBySeqNumDesc(task.getTaskId())
                .map(TaskEventEntity::getSeqNum)
                .orElse(0L) + 1L;
        return Math.max(fromTask, fromEvents);
    }

    private boolean isTaskSeqDuplicate(DataIntegrityViolationException ex) {
        Throwable current = ex;
        while (current != null) {
            String message = current.getMessage();
            if (message != null && message.contains("uq_task_events_task_seq")) {
                return true;
            }
            current = current.getCause();
        }
        return false;
    }

    private void saveEvent(TaskEvent event) {
        TaskEventEntity eventEntity = new TaskEventEntity();
        eventEntity.setEventId(event.getEventId());
        eventEntity.setTaskId(event.getTaskId());
        eventEntity.setSessionId(event.getSessionId());
        eventEntity.setAssistant(event.getAssistant());
        eventEntity.setEventType(event.getType());
        eventEntity.setEventTimestamp(event.getTimestamp());
        eventEntity.setPayloadJson(writePayload(event.getPayload()));
        eventEntity.setSeqNum(event.getSeq());
        eventEntity.setEventVersion(event.getEventVersion());
        taskEventRepository.save(eventEntity);
    }

    private TaskEvent toProtocolEvent(TaskEventEntity eventEntity) {
        TaskEvent event = new TaskEvent();
        event.setEventId(eventEntity.getEventId());
        event.setTaskId(eventEntity.getTaskId());
        event.setSessionId(eventEntity.getSessionId());
        event.setAssistant(eventEntity.getAssistant());
        event.setType(eventEntity.getEventType());
        event.setTimestamp(eventEntity.getEventTimestamp());
        event.setPayload(readPayload(eventEntity.getPayloadJson()));
        event.setSeq(eventEntity.getSeqNum());
        event.setEventVersion(eventEntity.getEventVersion());
        return event;
    }

    private String writePayload(Map<String, Object> payload) {
        try {
            return objectMapper.writeValueAsString(payload == null ? Map.of() : payload);
        } catch (JsonProcessingException ex) {
            throw new IllegalStateException("failed to serialize event payload", ex);
        }
    }

    private Map<String, Object> readPayload(String payloadJson) {
        if (payloadJson == null || payloadJson.isBlank()) {
            return new HashMap<>();
        }
        try {
            return objectMapper.readValue(payloadJson, new TypeReference<>() {
            });
        } catch (JsonProcessingException ex) {
            throw new IllegalStateException("failed to parse event payload json", ex);
        }
    }

    private ApprovalDecision parseDecision(String rawDecision) {
        if (rawDecision == null) {
            return ApprovalDecision.PENDING;
        }
        return switch (rawDecision.toLowerCase()) {
            case "approve", "approved" -> ApprovalDecision.APPROVE;
            case "reject", "rejected" -> ApprovalDecision.REJECT;
            default -> ApprovalDecision.PENDING;
        };
    }

    private boolean isTerminal(TaskStatus status) {
        return stateMachine.isTerminal(status);
    }

    private String randomId() {
        return UUID.randomUUID().toString().replace("-", "");
    }
}
