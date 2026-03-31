package com.autocode.controlplane;

import com.autocode.controlplane.api.CreateTaskRequest;
import com.autocode.controlplane.persistence.repo.TaskEntityRepository;
import com.autocode.controlplane.service.TaskService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;

@SpringBootTest
class IdempotencyConcurrencyTest {

    @Autowired
    private TaskService taskService;

    @Autowired
    private TaskEntityRepository taskRepository;

    @Test
    void sameIdempotencyKeyConcurrentShouldReturnSameTaskId() throws Exception {
        CreateTaskRequest req = new CreateTaskRequest();
        req.setProjectId("proj-1");
        req.setAssistant("codex");
        req.setPrompt("concurrency idem");

        String idemKey = "idem-cc-1";

        CountDownLatch ready = new CountDownLatch(2);
        CountDownLatch start = new CountDownLatch(1);

        var pool = Executors.newFixedThreadPool(2);
        try {
            Future<String> f1 = pool.submit(() -> {
                ready.countDown();
                start.await();
                return taskService.createTask(req, idemKey).getTaskId();
            });
            Future<String> f2 = pool.submit(() -> {
                ready.countDown();
                start.await();
                return taskService.createTask(req, idemKey).getTaskId();
            });
            ready.await();
            start.countDown();

            String t1 = f1.get();
            String t2 = f2.get();
            assertEquals(t1, t2);
            assertNotNull(taskRepository.findById(t1).orElse(null));
        } finally {
            pool.shutdownNow();
        }
    }
}

