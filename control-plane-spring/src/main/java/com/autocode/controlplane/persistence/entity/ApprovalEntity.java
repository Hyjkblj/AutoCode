/**
 * JPA entity representing an approval record associated with a task.
 */
package com.autocode.controlplane.persistence.entity;

import com.autocode.protocol.model.ApprovalDecision;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.Instant;

@Entity
@Table(name = "approvals")
public class ApprovalEntity {
    @Id
    @Column(name = "approval_id", nullable = false, length = 64)
    private String approvalId;

    @Column(name = "task_id", nullable = false, length = 64)
    private String taskId;

    @Enumerated(EnumType.STRING)
    @Column(name = "decision", nullable = false, length = 32)
    private ApprovalDecision decision;

    @Column(name = "comment_text", columnDefinition = "TEXT")
    private String commentText;

    @Column(name = "approval_context_json", columnDefinition = "TEXT")
    private String approvalContextJson;

    @Column(name = "decided_at")
    private Instant decidedAt;

    public String getApprovalId() {
        return approvalId;
    }

    public void setApprovalId(String approvalId) {
        this.approvalId = approvalId;
    }

    public String getTaskId() {
        return taskId;
    }

    public void setTaskId(String taskId) {
        this.taskId = taskId;
    }

    public ApprovalDecision getDecision() {
        return decision;
    }

    public void setDecision(ApprovalDecision decision) {
        this.decision = decision;
    }

    public String getCommentText() {
        return commentText;
    }

    public void setCommentText(String commentText) {
        this.commentText = commentText;
    }

    public String getApprovalContextJson() {
        return approvalContextJson;
    }

    public void setApprovalContextJson(String approvalContextJson) {
        this.approvalContextJson = approvalContextJson;
    }

    public Instant getDecidedAt() {
        return decidedAt;
    }

    public void setDecidedAt(Instant decidedAt) {
        this.decidedAt = decidedAt;
    }
}
