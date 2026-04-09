package com.autocode.agent.runtime;

import com.autocode.protocol.model.ArtifactMetadata;
import com.autocode.protocol.model.TaskSummary;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class TaskExecutorDeployReportingTest {

    @Test
    void isDeployEnabledUsesEnvFlagOrEnvironment() {
        assertFalse(TaskExecutor.isDeployEnabled(Map.of()));
        assertTrue(TaskExecutor.isDeployEnabled(Map.of("MVP_DEPLOY_ENABLED", "true")));
        assertTrue(TaskExecutor.isDeployEnabled(Map.of("MVP_DEPLOY_ENVIRONMENT", "staging")));
    }

    @Test
    void buildDeployContextIncludesRequiredFields() {
        TaskSummary task = new TaskSummary();
        task.setTaskId("task_123");
        task.setProjectId("proj_123");
        task.setPrompt("deploy to staging");

        ArtifactMetadata artifact = new ArtifactMetadata();
        artifact.setArtifactId("art_123");
        artifact.setType("zip");

        Map<String, Object> context = TaskExecutor.buildDeployContext(
                task,
                "D:/workspace/proj",
                "dep_req_123",
                artifact,
                Map.of("MVP_DEPLOY_TOOL", "deploy.execute")
        );

        assertEquals("app.publish", context.get("action"));
        assertEquals("deploy.execute", context.get("tool"));
        assertEquals("D:/workspace/proj", context.get("workspaceRef"));
        Object inputsHash = context.get("inputsHash");
        assertNotNull(inputsHash);
        assertTrue(inputsHash instanceof String);
        assertTrue(((String) inputsHash).startsWith("sha256:"));
    }

    @Test
    void buildDeployPlanPayloadContainsRequiredContractFields() {
        ArtifactMetadata artifact = new ArtifactMetadata();
        artifact.setArtifactId("art_plan_1");
        artifact.setType("zip");
        artifact.setName("export.zip");

        Map<String, Object> context = new HashMap<>();
        context.put("action", "app.publish");
        context.put("tool", "deploy.execute");
        context.put("workspaceRef", "workspace://proj-1");
        context.put("inputsHash", "sha256:abc");

        Map<String, Object> payload = TaskExecutor.buildDeployPlanPayload(
                "dep_req_1",
                "staging",
                artifact,
                context,
                Map.of(
                        "MVP_DEPLOY_STRATEGY", "rolling",
                        "MVP_DEPLOY_TRIGGERED_BY", "user:operator_1",
                        "MVP_DEPLOY_OPTION_PROVIDER", "vercel"
                )
        );

        assertEquals("dep_req_1", payload.get("requestId"));
        assertEquals("staging", payload.get("environment"));
        assertEquals("rolling", payload.get("strategy"));
        assertEquals("user:operator_1", payload.get("triggeredBy"));
        assertEquals(context, payload.get("context"));
        @SuppressWarnings("unchecked")
        Map<String, Object> artifactPayload = (Map<String, Object>) payload.get("artifact");
        assertEquals("art_plan_1", artifactPayload.get("artifactId"));
        assertEquals("zip", artifactPayload.get("type"));
    }

    @Test
    void buildDeployResultPayloadIncludesResultArtifact() {
        ArtifactMetadata resultArtifact = new ArtifactMetadata();
        resultArtifact.setArtifactId("art_result_1");
        resultArtifact.setType("deploy_report");
        resultArtifact.setMime("application/json");

        Map<String, Object> payload = TaskExecutor.buildDeployResultPayload(
                "dep_req_1",
                "staging",
                "success",
                "deployment completed",
                Map.of("MVP_DEPLOY_ENDPOINT_URL", "https://example.test/app"),
                resultArtifact,
                Instant.parse("2026-04-04T08:01:00Z"),
                Instant.parse("2026-04-04T08:02:30Z")
        );

        assertEquals("dep_req_1", payload.get("requestId"));
        assertEquals("success", payload.get("status"));
        assertEquals("staging", payload.get("environment"));
        assertEquals("https://example.test/app", payload.get("endpointUrl"));
        assertNotNull(payload.get("deploymentId"));
        assertEquals("2026-04-04T08:01:00Z", payload.get("startedAt"));
        assertEquals("2026-04-04T08:02:30Z", payload.get("finishedAt"));
        @SuppressWarnings("unchecked")
        Map<String, Object> resultArtifactPayload = (Map<String, Object>) payload.get("resultArtifact");
        assertEquals("art_result_1", resultArtifactPayload.get("artifactId"));
        assertEquals("deploy_report", resultArtifactPayload.get("type"));
    }

    @Test
    void buildDeployApprovalPayloadContainsRiskAndRequiredPolicies() {
        Map<String, Object> context = Map.of(
                "action", "app.publish",
                "tool", "deploy.execute",
                "workspaceRef", "workspace://proj-1",
                "inputsHash", "sha256:abc"
        );

        Map<String, Object> payload = TaskExecutor.buildDeployApprovalPayload(
                "apr_1",
                "deploy --env staging",
                "D:/workspace/proj-1",
                context,
                120,
                Map.of("MVP_DEPLOY_APPROVAL_RISK_SCORE", "0.99")
        );

        assertEquals("apr_1", payload.get("approvalId"));
        assertEquals(0.99d, payload.get("riskScore"));
        @SuppressWarnings("unchecked")
        List<String> requiredPolicies = (List<String>) payload.get("requiredPolicies");
        assertEquals(List.of("approval.gate", "deploy.context.match"), requiredPolicies);
    }

    @Test
    void buildDeployContextNormalizesWorkspaceRefAndKeepsHashStableAcrossSeparators() {
        TaskSummary task = new TaskSummary();
        task.setTaskId("task_456");
        task.setProjectId("proj_456");
        task.setPrompt("deploy now");

        ArtifactMetadata artifact = new ArtifactMetadata();
        artifact.setArtifactId("art_456");
        artifact.setType("zip");

        Map<String, Object> windowsContext = TaskExecutor.buildDeployContext(
                task,
                "D:\\workspace\\proj",
                "dep_req_456",
                artifact,
                Map.of()
        );

        Map<String, Object> unixContext = TaskExecutor.buildDeployContext(
                task,
                "D:/workspace/proj",
                "dep_req_456",
                artifact,
                Map.of()
        );

        assertEquals("D:/workspace/proj", windowsContext.get("workspaceRef"));
        assertEquals("D:/workspace/proj", unixContext.get("workspaceRef"));
        assertEquals(windowsContext.get("inputsHash"), unixContext.get("inputsHash"));
    }
}
