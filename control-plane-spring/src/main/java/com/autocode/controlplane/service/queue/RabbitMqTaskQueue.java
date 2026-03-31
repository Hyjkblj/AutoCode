/**
 * RabbitMQ-backed queue adapter (simple work queue semantics).
 */
package com.autocode.controlplane.service.queue;

import org.springframework.amqp.core.Queue;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.stereotype.Component;

@Component
@ConditionalOnProperty(prefix = "mvp.queue", name = "backend", havingValue = "rabbit")
public class RabbitMqTaskQueue implements TaskQueuePort {
    private final RabbitTemplate rabbitTemplate;
    private final String queueName;

    public RabbitMqTaskQueue(RabbitTemplate rabbitTemplate) {
        this.rabbitTemplate = rabbitTemplate;
        this.queueName = System.getProperty("mvp.queue.rabbit.queue", "mvp-task-queue");
    }

    @Bean
    public Queue mvpTaskQueue() {
        return new Queue(queueName, true);
    }

    @Override
    public void enqueue(String taskId) {
        rabbitTemplate.convertAndSend(queueName, taskId);
    }

    @Override
    public TaskQueueMessage pollMessage() {
        Object msg = rabbitTemplate.receiveAndConvert(queueName);
        if (msg == null) {
            return null;
        }
        String taskId = String.valueOf(msg);
        // Using RabbitTemplate.receiveAndConvert already removes the message from the queue,
        // so ack/nack are best-effort at this abstraction layer.
        return new TaskQueueMessage(taskId, "rcpt_" + taskId);
    }

    @Override
    public void ack(String receipt) {
        // no-op for now (message already removed)
    }

    @Override
    public void nack(String receipt, boolean requeue) {
        // Best-effort: cannot retrieve original message body from receipt, so no requeue here.
        // Production should use listener container + manual acks with delivery tags.
    }
}

