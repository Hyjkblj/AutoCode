package com.autocode.agent.sandbox;

import com.autocode.agent.client.AgentApiClient;
import com.autocode.agent.config.AgentConfig;
import com.autocode.protocol.model.ApprovalDecision;
import com.autocode.protocol.model.EventType;
import com.autocode.protocol.model.TaskEvent;
import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class SandboxExecutionServiceTest {

    @Test
    void executeRunsCommandAndPublishesToolEvents() throws Exception {
        Path workspace = Files.createTempDirectory("sandbox-exec-ok");
        RecordingAgentApiClient apiClient = new RecordingAgentApiClient();
        SandboxExecutionService service = new SandboxExecutionService(apiClient, configWithWorkspace(workspace));

        SandboxExecuteRequest request = newRequest("task_ok", "echo sandbox_ok", workspace);
        request.setTraceId("trc_task_ok");
        request.setRunId("run_task_ok");

        SandboxExecuteResponse response = service.execute(request);

        assertTrue(response.isOk());
        assertEquals("ok", response.getStatus());
        assertEquals(0, response.getExitCode());
        assertTrue(response.getOutput().contains("sandbox_ok"));
        assertEquals("command.exec", response.getTool());
        assertEquals("1.0.0", response.getToolVersion());

        List<EventType> types = apiClient.eventTypes();
        assertEquals(List.of(EventType.TOOL_START, EventType.TOOL_END), types);
        assertEquals("trc_task_ok", apiClient.events().get(0).getPayload().get("traceId"));
        assertEquals("run_task_ok", apiClient.events().get(0).getPayload().get("runId"));
    }

    @Test
    void executeApprovalFlowPublishesApprovalEventsThenRunsToolWhenApproved() throws Exception {
        Path workspace = Files.createTempDirectory("sandbox-exec-approve");
        RecordingAgentApiClient apiClient = new RecordingAgentApiClient(ApprovalDecision.APPROVE);
        SandboxExecutionService service = new SandboxExecutionService(apiClient, configWithWorkspace(workspace));

        SandboxExecuteRequest request = newRequest("task_approve", "echo deploy_now", workspace);
        request.setPrompt("please deploy this");

        SandboxExecuteResponse response = service.execute(request);

        assertTrue(response.isOk());
        List<EventType> types = apiClient.eventTypes();
        assertEquals(List.of(
                EventType.APPROVAL_REQUIRED,
                EventType.APPROVAL_RESULT,
                EventType.TOOL_START,
                EventType.TOOL_END
        ), types);
        assertEquals("approve", apiClient.events().get(1).getPayload().get("decision"));
    }

    @Test
    void executeReturnsRejectedWhenApprovalDenied() throws Exception {
        Path workspace = Files.createTempDirectory("sandbox-exec-reject");
        RecordingAgentApiClient apiClient = new RecordingAgentApiClient(ApprovalDecision.REJECT);
        SandboxExecutionService service = new SandboxExecutionService(apiClient, configWithWorkspace(workspace));

        SandboxExecuteRequest request = newRequest("task_reject", "echo deploy_reject", workspace);

        SandboxExecuteResponse response = service.execute(request);

        assertFalse(response.isOk());
        assertEquals("approval_rejected", response.getStatus());
        assertEquals("approval_rejected", response.getReason());

        List<EventType> types = apiClient.eventTypes();
        assertEquals(List.of(EventType.APPROVAL_REQUIRED, EventType.APPROVAL_RESULT), types);
    }

    @Test
    void executeDeniesWhenWorkspaceOutsideAllowlist() throws Exception {
        Path allowedWorkspace = Files.createTempDirectory("sandbox-allowed");
        Path blockedWorkspace = Files.createTempDirectory("sandbox-blocked");
        RecordingAgentApiClient apiClient = new RecordingAgentApiClient();
        SandboxExecutionService service = new SandboxExecutionService(apiClient, configWithWorkspace(allowedWorkspace));

        SandboxExecuteRequest request = newRequest("task_denied", "echo blocked", blockedWorkspace);

        SandboxExecuteResponse response = service.execute(request);

        assertFalse(response.isOk());
        assertEquals("denied", response.getStatus());
        assertTrue(response.getReason().startsWith("policy_denied:"));
        assertTrue(apiClient.events().isEmpty());
    }

    private static SandboxExecuteRequest newRequest(String taskId, String command, Path cwd) {
        SandboxExecuteRequest request = new SandboxExecuteRequest();
        request.setTaskId(taskId);
        request.setCommand(command);
        request.setCwd(cwd.toString());
        request.setPrompt("run");
        request.setAssistant("python-agent");
        request.setSessionId("sess_1");
        return request;
    }

    private static AgentConfig configWithWorkspace(Path workspacePrefix) {
        return new AgentConfig(
                "http://localhost:8048",
                "node-sandbox-test",
                "agent-test-token",
                200,
                500,
                1,
                List.of("echo"),
                List.of(workspacePrefix.toString()),
                "coder",
                true);
    }

    private static final class RecordingAgentApiClient extends AgentApiClient {
        private final ArrayList<TaskEvent> events = new ArrayList<>();
        private final ArrayDeque<ApprovalDecision> decisions = new ArrayDeque<>();

        private RecordingAgentApiClient(ApprovalDecision... approvalDecisions) {
            super("http://localhost:8048", "sandbox-token");
            if (approvalDecisions != null) {
                for (ApprovalDecision decision : approvalDecisions) {
                    decisions.add(decision);
                }
            }
        }

        @Override
        public void publishEvent(String taskId, TaskEvent event) {
            events.add(event);
        }

        @Override
        public ApprovalDecision getApprovalDecision(String taskId) {
            if (decisions.isEmpty()) {
                return ApprovalDecision.PENDING;
            }
            return decisions.removeFirst();
        }

        private List<TaskEvent> events() {
            return List.copyOf(events);
        }

        private List<EventType> eventTypes() {
            return events.stream().map(TaskEvent::getType).toList();
        }
    }
}
