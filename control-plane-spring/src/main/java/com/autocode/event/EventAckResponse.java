/**
 * ACK response DTO containing sequence number, acceptance status, and duplicate detection.
 * Implements Requirements 2.4 (Event ACK Protocol Compliance).
 */
package com.autocode.event;

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