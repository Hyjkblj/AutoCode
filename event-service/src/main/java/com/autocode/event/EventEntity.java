package com.autocode.event;

import jakarta.persistence.*;
import java.time.Instant;

/**
 * JPA entity representing a persisted event in the Event Service.
 * Implements Requirements 2.4, 2.5, 2.6 (Event persistence, deduplication, sequence continuity).
 */
@Entity
@Table(name = "events", indexes = {
        @Index(name = "idx_events_task_seq", columnList = "task_id,seq_num"),
        @Index(name = "idx_events_timestamp", columnList = "event_timestamp")
})
public class EventEntity {
    
    @Id
    @Column(name = "event_id", nullable = false, length = 64)
    private String eventId;

    @Column(name = "task_id", nullable = false, length = 64)
    private String taskId;

    @Column(name = "session_id", nullable = false, length = 64)
    private String sessionId;

    @Column(name = "assistant", nullable = false, length = 64)
    private String assistant;

    @Column(name = "event_type", nullable = false, length = 64)
    private String eventType;

    @Column(name = "event_timestamp", nullable = false)
    private Instant eventTimestamp;

    @Column(name = "payload_json", columnDefinition = "TEXT")
    private String payloadJson;

    @Column(name = "seq_num", nullable = false)
    private long seqNum;

    @Column(name = "event_version", nullable = false)
    private int eventVersion;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    @Column(name = "node_id", length = 64)
    private String nodeId;

    // Constructors
    public EventEntity() {
        this.createdAt = Instant.now();
    }

    // Getters and Setters
    public String getEventId() {
        return eventId;
    }

    public void setEventId(String eventId) {
        this.eventId = eventId;
    }

    public String getTaskId() {
        return taskId;
    }

    public void setTaskId(String taskId) {
        this.taskId = taskId;
    }

    public String getSessionId() {
        return sessionId;
    }

    public void setSessionId(String sessionId) {
        this.sessionId = sessionId;
    }

    public String getAssistant() {
        return assistant;
    }

    public void setAssistant(String assistant) {
        this.assistant = assistant;
    }

    public String getEventType() {
        return eventType;
    }

    public void setEventType(String eventType) {
        this.eventType = eventType;
    }

    public Instant getEventTimestamp() {
        return eventTimestamp;
    }

    public void setEventTimestamp(Instant eventTimestamp) {
        this.eventTimestamp = eventTimestamp;
    }

    public String getPayloadJson() {
        return payloadJson;
    }

    public void setPayloadJson(String payloadJson) {
        this.payloadJson = payloadJson;
    }

    public long getSeqNum() {
        return seqNum;
    }

    public void setSeqNum(long seqNum) {
        this.seqNum = seqNum;
    }

    public int getEventVersion() {
        return eventVersion;
    }

    public void setEventVersion(int eventVersion) {
        this.eventVersion = eventVersion;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(Instant createdAt) {
        this.createdAt = createdAt;
    }

    public String getNodeId() {
        return nodeId;
    }

    public void setNodeId(String nodeId) {
        this.nodeId = nodeId;
    }
}
