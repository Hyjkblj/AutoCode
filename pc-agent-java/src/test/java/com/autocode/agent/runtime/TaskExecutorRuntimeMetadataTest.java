package com.autocode.agent.runtime;

import com.autocode.protocol.model.ArtifactMetadata;
import com.autocode.protocol.model.ServiceRuntimeDescriptor;
import com.autocode.protocol.model.TaskSummary;
import com.autocode.protocol.validation.ServiceRuntimeDescriptorContractValidator;
import org.junit.jupiter.api.Test;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class TaskExecutorRuntimeMetadataTest {

    @Test
    void runtimeDescriptorBuildsFromEnvSignals() {
        Map<String, String> env = new HashMap<>();
        env.put("MVP_RUNTIME_SERVICE_ID", "control-plane-api");
        env.put("MVP_RUNTIME_PORT", "8080");
        env.put("MVP_RUNTIME_HEALTH_PATH", "/actuator/health");
        env.put("MVP_RUNTIME_START_COMMAND", "mvn -pl control-plane-spring spring-boot:run");

        ServiceRuntimeDescriptor descriptor = TaskExecutor.buildRuntimeDescriptor(
                task("task_1"),
                "ignored",
                "D:/workspace/control-plane-spring",
                env
        );

        assertNotNull(descriptor);
        assertEquals(1, descriptor.getSchemaVersion());
        assertEquals("control-plane-api", descriptor.getServiceId());
        assertNotNull(descriptor.getPorts());
        assertEquals(8080, descriptor.getPorts().get(0).getPort());
        assertEquals("/actuator/health", descriptor.getHealthCheck().getPath());
        assertEquals("GET", descriptor.getHealthCheck().getMethod());
        assertEquals("mvn -pl control-plane-spring spring-boot:run", descriptor.getStartup().getCommand());
        assertDoesNotThrow(() -> ServiceRuntimeDescriptorContractValidator.validate(descriptor));
    }

    @Test
    void runtimeDescriptorDisabledWhenNoSignals() {
        ServiceRuntimeDescriptor descriptor = TaskExecutor.buildRuntimeDescriptor(
                task("task_2"),
                "mvn test",
                "D:/workspace",
                Map.of()
        );
        assertNull(descriptor);
    }

    @Test
    void runDescriptorSynthesizesHealthHint() {
        Map<String, String> env = new HashMap<>();
        env.put("MVP_RUNTIME_PORT", "8080");
        env.put("MVP_RUNTIME_HEALTH_PATH", "actuator/health");
        env.put("MVP_RUNTIME_RUN_HINTS", "log:tail,log:tail");

        ArtifactMetadata.RunDescriptor run = TaskExecutor.buildRunDescriptor(
                null,
                "mvn -pl control-plane-spring spring-boot:run",
                env
        );

        assertNotNull(run);
        assertEquals("mvn -pl control-plane-spring spring-boot:run", run.getCommand());
        assertNotNull(run.getHints());
        assertTrue(run.getHints().contains("http://127.0.0.1:8080/actuator/health"));
        assertEquals(List.of("http://127.0.0.1:8080/actuator/health", "log:tail"), run.getHints());
    }

    private static TaskSummary task(String taskId) {
        TaskSummary task = new TaskSummary();
        task.setTaskId(taskId);
        task.setAssistant("codex");
        task.setSessionKey("sess_" + taskId);
        return task;
    }
}
