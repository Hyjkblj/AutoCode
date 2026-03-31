/**
 * Pure in-memory task queue (no external dependencies).
 */
package com.autocode.controlplane.service.queue;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

import java.util.Map;
import java.util.Queue;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentLinkedQueue;

@Component
@ConditionalOnProperty(prefix = "mvp.queue", name = "backend", havingValue = "inmem")
public class InMemoryTaskQueue implements TaskQueuePort {
    private final Queue<String> queue = new ConcurrentLinkedQueue<>();
    private final Map<String, String> inFlight = new ConcurrentHashMap<>();

    @Override
    public void enqueue(String taskId) {
        queue.offer(taskId);
    }

    @Override
    public TaskQueueMessage pollMessage() {
        String taskId = queue.poll();
        if (taskId == null) {
            return null;
        }
        String receipt = "rcpt_" + taskId;
        inFlight.put(receipt, taskId);
        return new TaskQueueMessage(taskId, receipt);
    }

    @Override
    public void ack(String receipt) {
        if (receipt == null) return;
        inFlight.remove(receipt);
    }

    @Override
    public void nack(String receipt, boolean requeue) {
        if (receipt == null) return;
        String taskId = inFlight.remove(receipt);
        if (requeue && taskId != null) {
            queue.offer(taskId);
        }
    }
}

