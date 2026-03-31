/**
 * Abstraction for the task queue used to dispatch work to agent nodes.
 */
package com.autocode.controlplane.service.queue;

public interface TaskQueuePort {
    void enqueue(String taskId);

    /**
     * Polls one message from the queue. The returned message must be acked/nacked if non-null.
     */
    TaskQueueMessage pollMessage();

    /**
     * Acknowledge successful processing/claiming of the message.
     */
    void ack(String receipt);

    /**
     * Negative-acknowledge a message.
     *
     * @param requeue if true, message will be put back to the queue.
     */
    void nack(String receipt, boolean requeue);

    /**
     * Backward-compat convenience for older call sites.
     * Prefer {@link #pollMessage()} + {@link #ack(String)} / {@link #nack(String, boolean)}.
     */
    default String poll() {
        TaskQueueMessage msg = pollMessage();
        return msg == null ? null : msg.taskId();
    }
}
