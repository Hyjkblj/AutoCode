/**
 * Coarse task lifecycle states tracked by the control plane.
 */
package com.autocode.protocol.model;

public enum TaskStatus {
    QUEUED,
    RUNNING,
    WAITING_APPROVAL,
    PAUSED,
    DONE,
    FAILED,
    CANCELED
}
