package com.autocode.controlplane;

import com.autocode.controlplane.api.CreateTaskRequest;
import com.autocode.controlplane.persistence.repo.TaskEventEntityRepository;
import com.autocode.controlplane.service.TaskService;
import com.autocode.protocol.model.EventType;
import com.autocode.protocol.model.TaskEvent;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

@SpringBootTest
class EventIngestConcurrencyTest {

    @Autowired
    private TaskService taskService;

    @Autowired
    private TaskEventEntityRepository taskEventRepo;

    @Test
    void concurrentIngestShouldAllocateMonotonicSeq() throws Exception {
        CreateTaskRequest req = new CreateTaskRequest();
        req.setProjectId("proj-1");
        req.setAssistant("codex");
        req.setPrompt("concurrency ingest");
        String taskId = taskService.createTask(req, null).getTaskId();

        TaskEvent e1 = new TaskEvent();
        e1.setEventId("evt-conc-1");
        e1.setType(EventType.ASSISTANT_OUTPUT);
        e1.setAssistant("codex");
        e1.getPayload().put("message", "m1");

        TaskEvent e2 = new TaskEvent();
        e2.setEventId("evt-conc-2");
        e2.setType(EventType.ASSISTANT_OUTPUT);
        e2.setAssistant("codex");
        e2.getPayload().put("message", "m2");

        CountDownLatch ready = new CountDownLatch(2);
        CountDownLatch start = new CountDownLatch(1);

        var pool = Executors.newFixedThreadPool(2);
        try {
            Future<?> f1 = pool.submit(() -> {
                ready.countDown();
                start.await();
                taskService.ingestAgentEvent(taskId, e1);
                return null;
            });
            Future<?> f2 = pool.submit(() -> {
                ready.countDown();
                start.await();
                taskService.ingestAgentEvent(taskId, e2);
                return null;
            });
            ready.await();
            start.countDown();
            f1.get();
            f2.get();
        } finally {
            pool.shutdownNow();
        }

        var events = taskEventRepo.findByTaskIdOrderBySeqNumAsc(taskId);
        var ours = events.stream()
                .filter(e -> "evt-conc-1".equals(e.getEventId()) || "evt-conc-2".equals(e.getEventId()))
                .toList();
        assertEquals(2, ours.size());
        long s1 = ours.get(0).getSeqNum();
        long s2 = ours.get(1).getSeqNum();
        assertTrue(s1 > 0 && s2 > 0);
        assertEquals(1, Math.abs(s1 - s2));
    }
}

