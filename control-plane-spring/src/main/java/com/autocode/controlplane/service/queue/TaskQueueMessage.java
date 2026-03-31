package com.autocode.controlplane.service.queue;

/**
 * Represents a polled queue item with an acknowledgement handle ("receipt").
 *
 * For some backends, receipt may equal taskId; for others it may be a message id.
 */
public record TaskQueueMessage(String taskId, String receipt) {
}

