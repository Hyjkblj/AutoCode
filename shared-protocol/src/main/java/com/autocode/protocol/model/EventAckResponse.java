/**
 * Shared ACK response DTO for the event ingestion protocol.
 * Both control-plane and event-service must return this structure.
 * Python agent parses this exact shape.
 */
package com.autocode.protocol.model;

import com.fasterxml.jackson.annotation.JsonProperty;

public class EventAckResponse {
    @JsonProperty("seq")
    private final long sequenceNumber;

    @JsonProperty("accepted")
    private final boolean accepted;

    @JsonProperty("duplicate")
    private final boolean duplicate;

    @JsonProperty("errorCode")
    private final String errorCode;

    public EventAckResponse(long sequenceNumber, boolean accepted, boolean duplicate, String errorCode) {
        this.sequenceNumber = sequenceNumber;
        this.accepted = accepted;
        this.duplicate = duplicate;
        this.errorCode = errorCode;
    }

    public static EventAckResponse accepted(long seq) {
        return new EventAckResponse(seq, true, false, null);
    }

    public static EventAckResponse duplicate(long seq) {
        return new EventAckResponse(seq, true, true, null);
    }

    public static EventAckResponse rejected(AckErrorCode errorCode) {
        return new EventAckResponse(0L, false, false, errorCode.name());
    }

    public static EventAckResponse rejected(AckErrorCode errorCode, long seq) {
        return new EventAckResponse(seq, false, false, errorCode.name());
    }

    public long getSequenceNumber() {
        return sequenceNumber;
    }

    public boolean isAccepted() {
        return accepted;
    }

    public boolean isDuplicate() {
        return duplicate;
    }

    public String getErrorCode() {
        return errorCode;
    }

    @Override
    public String toString() {
        return "EventAckResponse{" +
                "seq=" + sequenceNumber +
                ", accepted=" + accepted +
                ", duplicate=" + duplicate +
                ", errorCode='" + errorCode + '\'' +
                '}';
    }
}
