/**
 * Integration tests covering approval flow, cancel behavior, and event deduplication.
 */
package com.autocode.controlplane;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Disabled;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;

import java.util.Iterator;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
class TaskWorkflowIntegrationTest extends OperatorProj1MembershipFixture {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private com.autocode.controlplane.persistence.repo.TaskEntityRepository taskEntityRepository;

    @Autowired
    private com.autocode.controlplane.service.queue.TaskQueuePort taskQueue;

    @Test
    void approvalFlowCanResumeAndCompleteTask() throws Exception {
        String createResponse = createTask("Implement guarded command execution");
        String taskId = objectMapper.readTree(createResponse).path("payload").path("taskId").asText();

        String approvalRequiredEvent = """
                {
                  "event": {
                    "eventId": "evt-approval-required-1",
                    "type": "APPROVAL_REQUIRED",
                    "assistant": "codex",
                    "payload": {
                      "approvalId": "apr-flow-1",
                      "action": "run_command",
                      "command": "git push origin main"
                    }
                  }
                }
                """;

        mockMvc.perform(post("/api/v1/agent/tasks/{taskId}/events", taskId)
                        .header("X-Agent-Token", "agent-dev-token")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(approvalRequiredEvent))
                .andExpect(status().isOk());

        mockMvc.perform(get("/api/v1/tasks/{taskId}", taskId)
                        .header("Authorization", "Bearer operator-dev-token"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.payload.status").value("WAITING_APPROVAL"));

        String approvalBody = """
                {
                  "approvalId": "apr-flow-1",
                  "decision": "approve",
                  "comment": "approved in integration test"
                }
                """;
        mockMvc.perform(post("/api/v1/tasks/{taskId}/approval", taskId)
                        .header("Authorization", "Bearer operator-dev-token")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(approvalBody))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.payload.status").value("RUNNING"));

        mockMvc.perform(get("/api/v1/agent/tasks/{taskId}/approval", taskId)
                        .header("X-Agent-Token", "agent-dev-token"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.payload.decision").value("approve"));

        String doneEvent = """
                {
                  "event": {
                    "eventId": "evt-done-1",
                    "type": "TASK_DONE",
                    "assistant": "codex",
                    "payload": {
                      "result": "success"
                    }
                  }
                }
                """;

        mockMvc.perform(post("/api/v1/agent/tasks/{taskId}/events", taskId)
                        .header("X-Agent-Token", "agent-dev-token")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(doneEvent))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.payload.status").value("DONE"));
    }

    @Test
    void profileRoutingShouldPreferMatchingProfile() throws Exception {
        String t1 = objectMapper.readTree(createTask("need coder")).path("payload").path("taskId").asText();
        String t2Payload = """
                {
                  "projectId": "proj-1",
                  "assistant": "codex",
                  "prompt": "need reviewer",
                  "agentProfile": "reviewer"
                }
                """;
        String t2Resp = mockMvc.perform(post("/api/v1/tasks")
                        .header("Authorization", "Bearer operator-dev-token")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(t2Payload))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();
        String t2 = objectMapper.readTree(t2Resp).path("payload").path("taskId").asText();

        // reviewer agent should be able to obtain reviewer task eventually.
        for (int i = 0; i < 20; i++) {
            var res = mockMvc.perform(get("/api/v1/agent/tasks/next")
                            .param("nodeId", "node-reviewer-1")
                            .param("profile", "reviewer")
                            .header("X-Agent-Token", "agent-dev-token"))
                    .andReturn();
            if (res.getResponse().getStatus() == 204) {
                continue;
            }
            String body = res.getResponse().getContentAsString();
            String got = objectMapper.readTree(body).path("payload").path("taskId").asText();
            if (t2.equals(got)) {
                return;
            }
        }
        org.junit.jupiter.api.Assertions.fail("reviewer profile did not receive reviewer task " + t2);
    }

    @Test
    void cancelTaskMarksCanceledAndWritesFailureEvent() throws Exception {
        String createResponse = createTask("Refactor null checks");
        String taskId = objectMapper.readTree(createResponse).path("payload").path("taskId").asText();

        mockMvc.perform(post("/api/v1/tasks/{taskId}/cancel", taskId)
                        .header("Authorization", "Bearer operator-dev-token"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.payload.status").value("CANCELED"));

        String eventsResponse = mockMvc.perform(get("/api/v1/tasks/{taskId}/events", taskId)
                        .header("Authorization", "Bearer operator-dev-token"))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();

        JsonNode events = objectMapper.readTree(eventsResponse).path("payload");
        boolean hasCancelFailureEvent = false;
        for (JsonNode event : events) {
            if ("TASK_FAILED".equals(event.path("type").asText())
                    && "user_cancel".equals(event.path("payload").path("reason").asText())) {
                hasCancelFailureEvent = true;
                break;
            }
        }
        assertTrue(hasCancelFailureEvent);
    }

    @Test
    void duplicateAgentEventShouldBeIgnored() throws Exception {
        String createResponse = createTask("Generate patch preview");
        String taskId = objectMapper.readTree(createResponse).path("payload").path("taskId").asText();

        String assistantOutputEvent = """
                {
                  "event": {
                    "eventId": "evt-dup-1",
                    "type": "ASSISTANT_OUTPUT",
                    "assistant": "codex",
                    "payload": {
                      "message": "first message"
                    }
                  }
                }
                """;

        mockMvc.perform(post("/api/v1/agent/tasks/{taskId}/events", taskId)
                        .header("X-Agent-Token", "agent-dev-token")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(assistantOutputEvent))
                .andExpect(status().isOk());

        mockMvc.perform(post("/api/v1/agent/tasks/{taskId}/events", taskId)
                        .header("X-Agent-Token", "agent-dev-token")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(assistantOutputEvent))
                .andExpect(status().isOk());

        String eventsResponse = mockMvc.perform(get("/api/v1/tasks/{taskId}/events", taskId)
                        .header("Authorization", "Bearer operator-dev-token"))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();

        JsonNode events = objectMapper.readTree(eventsResponse).path("payload");
        int assistantOutputCount = 0;
        Iterator<JsonNode> iterator = events.elements();
        while (iterator.hasNext()) {
            JsonNode event = iterator.next();
            if ("ASSISTANT_OUTPUT".equals(event.path("type").asText())) {
                assistantOutputCount++;
            }
        }
        assertEquals(1, assistantOutputCount);
    }

    @Test
    void approvalContextMismatchShouldFailTask() throws Exception {
        String createResponse = createTask("Mismatch approval context");
        String taskId = objectMapper.readTree(createResponse).path("payload").path("taskId").asText();

        String approvalRequiredEvent = """
                {
                  "event": {
                    "eventId": "evt-approval-required-mismatch-1",
                    "type": "APPROVAL_REQUIRED",
                    "assistant": "codex",
                    "payload": {
                      "approvalId": "apr-mismatch-1",
                      "action": "run_command",
                      "command": "echo push origin main",
                      "cwd": "D:/repoA"
                    }
                  }
                }
                """;
        mockMvc.perform(post("/api/v1/agent/tasks/{taskId}/events", taskId)
                        .header("X-Agent-Token", "agent-dev-token")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(approvalRequiredEvent))
                .andExpect(status().isOk());

        String approvalBody = """
                {
                  "approvalId": "apr-mismatch-1",
                  "decision": "approve",
                  "comment": "approved in integration test"
                }
                """;
        mockMvc.perform(post("/api/v1/tasks/{taskId}/approval", taskId)
                        .header("Authorization", "Bearer operator-dev-token")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(approvalBody))
                .andExpect(status().isOk());

        // Agent tries to start executing a different command/cwd than what was approved.
        String toolStartEvent = """
                {
                  "event": {
                    "eventId": "evt-tool-start-mismatch-1",
                    "type": "TOOL_START",
                    "assistant": "codex",
                    "payload": {
                      "tool": "command.exec",
                      "action": "run_command",
                      "command": "echo HACKED",
                      "cwd": "D:/repoB"
                    }
                  }
                }
                """;
        mockMvc.perform(post("/api/v1/agent/tasks/{taskId}/events", taskId)
                        .header("X-Agent-Token", "agent-dev-token")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(toolStartEvent))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.payload.status").value("FAILED"));
    }

    @Test
    @Transactional
    @Disabled("Flaky in shared queue integration suite; lease logic covered by service-level behavior.")
    void expiredLeaseTaskShouldBeRequeuedAndPollable() throws Exception {
        String createResponse = createTask("Lease expiry");
        String taskId = objectMapper.readTree(createResponse).path("payload").path("taskId").asText();

        // Simulate a node claimed the task but died: mark RUNNING with an expired lease.
        var task = taskEntityRepository.findById(taskId).orElseThrow();
        task.setStatus(com.autocode.protocol.model.TaskStatus.RUNNING);
        task.setAssignedNodeId("node-dead-1");
        task.setLeasedAt(Instant.now().minusSeconds(120));
        task.setLeaseExpiresAt(Instant.now().minusSeconds(60));
        taskEntityRepository.saveAndFlush(task);

        // Deterministic recovery: explicitly requeue when lease expired, then ensure it becomes pollable.
        int updated = taskEntityRepository.requeueIfLeaseExpired(taskId, Instant.now());
        assertEquals(1, updated);

        // Drain existing queue items to make assertion deterministic.
        for (int i = 0; i < 200; i++) {
            var result = mockMvc.perform(get("/api/v1/agent/tasks/next")
                            .param("nodeId", "node-local-1")
                            .header("X-Agent-Token", "agent-dev-token"))
                    .andReturn();
            if (result.getResponse().getStatus() == 204) {
                break;
            }
        }

        taskQueue.enqueue(taskId);

        mockMvc.perform(get("/api/v1/agent/tasks/next")
                        .param("nodeId", "node-local-1")
                        .header("X-Agent-Token", "agent-dev-token"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.payload.taskId").value(taskId))
                .andExpect(jsonPath("$.payload.assignedNodeId").value("node-local-1"));
    }

    private String createTask(String prompt) throws Exception {
        String createPayload = """
                {
                  "projectId": "proj-1",
                  "assistant": "codex",
                  "prompt": "%s"
                }
                """.formatted(prompt);
        return mockMvc.perform(post("/api/v1/tasks")
                        .header("Authorization", "Bearer operator-dev-token")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(createPayload))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();
    }
}
