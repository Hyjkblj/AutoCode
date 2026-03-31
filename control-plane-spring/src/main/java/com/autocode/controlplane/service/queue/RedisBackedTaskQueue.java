/**
 * Redis-backed queue with in-memory fallback for local resilience.
 */
package com.autocode.controlplane.service.queue;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

import java.util.Map;
import java.util.Queue;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentLinkedQueue;

@Component
@ConditionalOnProperty(prefix = "mvp.queue", name = "backend", havingValue = "redis", matchIfMissing = true)
public class RedisBackedTaskQueue implements TaskQueuePort {
    private static final Logger log = LoggerFactory.getLogger(RedisBackedTaskQueue.class);

    private final StringRedisTemplate redisTemplate;
    private final Queue<String> fallbackQueue = new ConcurrentLinkedQueue<>();
    private final Map<String, String> fallbackInFlight = new ConcurrentHashMap<>();
    private final String redisKey;
    private final String inflightKey;

    public RedisBackedTaskQueue(
            StringRedisTemplate redisTemplate,
            @Value("${mvp.queue.redis-key:mvp:task:queue}") String redisKey
    ) {
        this.redisTemplate = redisTemplate;
        this.redisKey = redisKey;
        this.inflightKey = redisKey + ":inflight";
    }

    @Override
    public void enqueue(String taskId) {
        try {
            redisTemplate.opsForList().rightPush(redisKey, taskId);
        } catch (Exception ex) {
            log.warn("Redis enqueue failed, falling back to in-memory queue: {}", ex.getMessage());
            fallbackQueue.offer(taskId);
        }
    }

    @Override
    public TaskQueueMessage pollMessage() {
        try {
            // Move from ready list to inflight list to approximate ack semantics.
            String taskId = redisTemplate.opsForList().leftPop(redisKey);
            if (taskId != null) {
                String receipt = "rcpt_" + UUID.randomUUID().toString().replace("-", "");
                redisTemplate.opsForHash().put(inflightKey, receipt, taskId);
                return new TaskQueueMessage(taskId, receipt);
            }
        } catch (Exception ex) {
            log.warn("Redis poll failed, fallback queue will be used: {}", ex.getMessage());
        }
        String taskId = fallbackQueue.poll();
        if (taskId == null) {
            return null;
        }
        String receipt = "rcpt_" + UUID.randomUUID().toString().replace("-", "");
        fallbackInFlight.put(receipt, taskId);
        return new TaskQueueMessage(taskId, receipt);
    }

    @Override
    public void ack(String receipt) {
        if (receipt == null || receipt.isBlank()) return;
        try {
            redisTemplate.opsForHash().delete(inflightKey, receipt);
            return;
        } catch (Exception ex) {
            log.warn("Redis ack failed, fallback inflight will be used: {}", ex.getMessage());
        }
        fallbackInFlight.remove(receipt);
    }

    @Override
    public void nack(String receipt, boolean requeue) {
        if (receipt == null || receipt.isBlank()) return;
        String taskId = null;
        try {
            Object raw = redisTemplate.opsForHash().get(inflightKey, receipt);
            if (raw != null) {
                taskId = String.valueOf(raw);
            }
            redisTemplate.opsForHash().delete(inflightKey, receipt);
        } catch (Exception ex) {
            log.warn("Redis nack failed, fallback inflight will be used: {}", ex.getMessage());
            taskId = fallbackInFlight.remove(receipt);
        }
        if (requeue && taskId != null && !taskId.isBlank()) {
            enqueue(taskId);
        }
    }
}
