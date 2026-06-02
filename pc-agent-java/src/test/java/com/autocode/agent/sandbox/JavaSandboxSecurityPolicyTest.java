package com.autocode.agent.sandbox;

import com.autocode.agent.client.AgentApiClient;
import com.autocode.agent.config.AgentConfig;
import com.autocode.agent.runtime.tool.ToolCall;
import com.autocode.agent.runtime.tool.ToolContext;
import com.autocode.agent.security.CommandSafetyPolicy;
import com.autocode.agent.security.policy.*;
import com.autocode.protocol.model.ApprovalDecision;
import com.autocode.protocol.model.SandboxExecuteRequest;
import com.autocode.protocol.model.SandboxExecuteResponse;
import com.autocode.protocol.model.TaskEvent;
import com.autocode.protocol.model.TaskSummary;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Comprehensive security policy tests for Java Sandbox.
 * 
 * **Validates: Requirements 6.4** (comprehensive test coverage for all core services)
 * 
 * Tests the following security policies:
 * - Command whitelisting enforcement
 * - Privilege escalation prevention
 * - Environment variable and network restrictions
 */
class JavaSandboxSecurityPolicyTest {

    // ========================================
    // Command Whitelisting Enforcement Tests
    // ========================================

    @Test
    void commandWhitelisting_AllowsWhitelistedCommand() {
        CommandSafetyPolicy policy = new CommandSafetyPolicy(List.of("echo", "ls", "pwd"));
        
        assertTrue(policy.isAllowed("echo hello world"));
        assertTrue(policy.isAllowed("ls -la"));
        assertTrue(policy.isAllowed("pwd"));
    }

    @Test
    void commandWhitelisting_DeniesNonWhitelistedCommand() {
        CommandSafetyPolicy policy = new CommandSafetyPolicy(List.of("echo", "ls"));
        
        assertFalse(policy.isAllowed("rm -rf /"));
        assertFalse(policy.isAllowed("cat /etc/passwd"));
        assertFalse(policy.isAllowed("chmod 777 file.txt"));
    }

    @Test
    void commandWhitelisting_EmptyWhitelistDeniesAll() {
        CommandSafetyPolicy policy = new CommandSafetyPolicy(List.of());
        
        assertFalse(policy.isAllowed("echo safe"));
        assertFalse(policy.isAllowed("ls"));
        assertFalse(policy.isAllowed("pwd"));
    }

    @Test
    void commandWhitelisting_IsCaseInsensitive() {
        CommandSafetyPolicy policy = new CommandSafetyPolicy(List.of("echo"));
        
        assertTrue(policy.isAllowed("echo test"));
        assertTrue(policy.isAllowed("ECHO test"));
        assertTrue(policy.isAllowed("Echo test"));
    }

    @Test
    void commandWhitelisting_MatchesPrefixNotSubstring() {
        CommandSafetyPolicy policy = new CommandSafetyPolicy(List.of("cat"));
        
        assertTrue(policy.isAllowed("cat file.txt"));
        // "concatenate" contains "cat" but doesn't start with it
        assertFalse(policy.isAllowed("concatenate files"));
    }

    @ParameterizedTest
    @ValueSource(strings = {
        "java -jar app.jar",
        "javac Main.java",
        "python script.py",
        "python3 test.py",
        "node index.js",
        "npm install"
    })
    void commandWhitelisting_AllowsCommonDevelopmentCommands(String command) {
        CommandSafetyPolicy policy = new CommandSafetyPolicy(
            List.of("java", "javac", "python", "python3", "node", "npm")
        );
        
        assertTrue(policy.isAllowed(command));
    }

    @Test
    void commandWhitelisting_IntegrationWithSandboxExecutionService(@TempDir Path workspace) throws Exception {
        RecordingAgentApiClient apiClient = new RecordingAgentApiClient();
        AgentConfig config = new AgentConfig(
            "http://localhost:8048",
            "test-node",
            "test-token",
            200,
            500,
            1,
            List.of("echo"), // Only allow echo
            List.of(workspace.toString()),
            "coder",
            true
        );
        SandboxExecutionService service = new SandboxExecutionService(apiClient, config);

        // Allowed command should succeed
        SandboxExecuteRequest allowedRequest = createRequest("task1", "echo allowed", workspace);
        SandboxExecuteResponse allowedResponse = service.execute(allowedRequest);
        assertTrue(allowedResponse.isOk());

        // Non-whitelisted command should be denied
        SandboxExecuteRequest deniedRequest = createRequest("task2", "cat /etc/passwd", workspace);
        SandboxExecuteResponse deniedResponse = service.execute(deniedRequest);
        assertFalse(deniedResponse.isOk());
        assertEquals("denied", deniedResponse.getStatus());
    }

    // ========================================
    // Privilege Escalation Prevention Tests
    // ========================================

    @Test
    void privilegeEscalation_DeniesSudoCommand() {
        ElevationDetectionPolicy policy = new ElevationDetectionPolicy();
        ToolCall call = new ToolCall("command.exec", "run_command", 
            Map.of("command", "sudo rm -rf /tmp/test"));
        ToolContext context = new ToolContext(new TaskSummary(), "/workspace", null, 120);
        
        PolicyDecision decision = policy.evaluate(call, context);
        
        assertFalse(decision.isAllowed());
        assertEquals("elevation_not_allowed", decision.getReason());
    }

    @Test
    void privilegeEscalation_DeniesSuCommand() {
        ElevationDetectionPolicy policy = new ElevationDetectionPolicy();
        ToolCall call = new ToolCall("command.exec", "run_command", 
            Map.of("command", "su root -c 'rm -rf /'"));
        ToolContext context = new ToolContext(new TaskSummary(), "/workspace", null, 120);
        
        PolicyDecision decision = policy.evaluate(call, context);
        
        assertFalse(decision.isAllowed());
        assertEquals("elevation_not_allowed", decision.getReason());
    }

    @Test
    void privilegeEscalation_DeniesRunasCommand() {
        ElevationDetectionPolicy policy = new ElevationDetectionPolicy();
        ToolCall call = new ToolCall("command.exec", "run_command", 
            Map.of("command", "runas /user:Administrator cmd"));
        ToolContext context = new ToolContext(new TaskSummary(), "/workspace", null, 120);
        
        PolicyDecision decision = policy.evaluate(call, context);
        
        assertFalse(decision.isAllowed());
        assertEquals("elevation_not_allowed", decision.getReason());
    }

    @Test
    void privilegeEscalation_DeniesPkexecCommand() {
        ElevationDetectionPolicy policy = new ElevationDetectionPolicy();
        ToolCall call = new ToolCall("command.exec", "run_command", 
            Map.of("command", "pkexec systemctl restart service"));
        ToolContext context = new ToolContext(new TaskSummary(), "/workspace", null, 120);
        
        PolicyDecision decision = policy.evaluate(call, context);
        
        assertFalse(decision.isAllowed());
        assertEquals("elevation_not_allowed", decision.getReason());
    }

    @Test
    void privilegeEscalation_DeniesPowerShellElevation() {
        ElevationDetectionPolicy policy = new ElevationDetectionPolicy();
        ToolCall call = new ToolCall("command.exec", "run_command", 
            Map.of("command", "powershell -verb runas -file script.ps1"));
        ToolContext context = new ToolContext(new TaskSummary(), "/workspace", null, 120);
        
        PolicyDecision decision = policy.evaluate(call, context);
        
        assertFalse(decision.isAllowed());
        assertEquals("elevation_not_allowed", decision.getReason());
    }

    @Test
    void privilegeEscalation_AllowsRegularCommands() {
        ElevationDetectionPolicy policy = new ElevationDetectionPolicy();
        ToolCall call = new ToolCall("command.exec", "run_command", 
            Map.of("command", "echo hello world"));
        ToolContext context = new ToolContext(new TaskSummary(), "/workspace", null, 120);
        
        PolicyDecision decision = policy.evaluate(call, context);
        
        assertTrue(decision.isAllowed());
    }

    @ParameterizedTest
    @ValueSource(strings = {
        "sudo apt-get install package",
        "su - user",
        "runas /user:Admin cmd",
        "pkexec bash",
        "doas command",
        "set-executionpolicy unrestricted"
    })
    void privilegeEscalation_DeniesAllElevationVariants(String command) {
        ElevationDetectionPolicy policy = new ElevationDetectionPolicy();
        ToolCall call = new ToolCall("command.exec", "run_command", 
            Map.of("command", command));
        ToolContext context = new ToolContext(new TaskSummary(), "/workspace", null, 120);
        
        PolicyDecision decision = policy.evaluate(call, context);
        
        assertFalse(decision.isAllowed());
        assertEquals("elevation_not_allowed", decision.getReason());
    }

    @Test
    void privilegeEscalation_IntegrationWithSandboxExecutionService(@TempDir Path workspace) throws Exception {
        RecordingAgentApiClient apiClient = new RecordingAgentApiClient();
        AgentConfig config = new AgentConfig(
            "http://localhost:8048",
            "test-node",
            "test-token",
            200,
            500,
            1,
            List.of("sudo", "echo"), // Allow sudo in whitelist but policy should block it
            List.of(workspace.toString()),
            "coder",
            true
        );
        SandboxExecutionService service = new SandboxExecutionService(apiClient, config);

        SandboxExecuteRequest request = createRequest("task_escalation", "sudo echo blocked", workspace);
        SandboxExecuteResponse response = service.execute(request);

        assertFalse(response.isOk());
        assertEquals("denied", response.getStatus());
        assertEquals("policy_denied:elevation_not_allowed", response.getReason());
        assertTrue(apiClient.events().isEmpty());
    }

    // ========================================
    // Environment Variable Restriction Tests
    // ========================================

    @Test
    void envVarRestriction_DeniesSensitiveEnvVarAccess() {
        EnvVarAccessPolicy policy = new EnvVarAccessPolicy();
        ToolCall call = new ToolCall("command.exec", "run_command", 
            Map.of("command", "echo $OPENAI_API_KEY"));
        ToolContext context = new ToolContext(new TaskSummary(), "/workspace", null, 120);
        
        PolicyDecision decision = policy.evaluate(call, context);
        
        assertFalse(decision.isAllowed());
        assertEquals("env_access_not_allowed", decision.getReason());
    }

    @ParameterizedTest
    @ValueSource(strings = {
        "echo $OPENAI_API_KEY",
        "echo $ANTHROPIC_API_KEY",
        "echo $AWS_SECRET_ACCESS_KEY",
        "echo $AWS_SESSION_TOKEN",
        "echo $GITHUB_TOKEN",
        "echo $MVP_AGENT_TOKEN",
        "echo $MVP_OPERATOR_TOKEN",
        "echo $MVP_JWT_SECRET"
    })
    void envVarRestriction_DeniesAllSensitiveEnvVars(String command) {
        EnvVarAccessPolicy policy = new EnvVarAccessPolicy();
        ToolCall call = new ToolCall("command.exec", "run_command", 
            Map.of("command", command));
        ToolContext context = new ToolContext(new TaskSummary(), "/workspace", null, 120);
        
        PolicyDecision decision = policy.evaluate(call, context);
        
        assertFalse(decision.isAllowed());
        assertEquals("env_access_not_allowed", decision.getReason());
    }

    @Test
    void envVarRestriction_AllowsNonSensitiveEnvVars() {
        EnvVarAccessPolicy policy = new EnvVarAccessPolicy();
        ToolCall call = new ToolCall("command.exec", "run_command", 
            Map.of("command", "echo $PATH"));
        ToolContext context = new ToolContext(new TaskSummary(), "/workspace", null, 120);
        
        PolicyDecision decision = policy.evaluate(call, context);
        
        assertTrue(decision.isAllowed());
    }

    @Test
    void envVarRestriction_IsCaseInsensitive() {
        EnvVarAccessPolicy policy = new EnvVarAccessPolicy();
        ToolCall call = new ToolCall("command.exec", "run_command", 
            Map.of("command", "echo $openai_api_key"));
        ToolContext context = new ToolContext(new TaskSummary(), "/workspace", null, 120);
        
        PolicyDecision decision = policy.evaluate(call, context);
        
        assertFalse(decision.isAllowed());
        assertEquals("env_access_not_allowed", decision.getReason());
    }

    @Test
    void envVarRestriction_SupportsCustomSensitiveKeys() {
        Set<String> customKeys = Set.of("MY_SECRET", "CUSTOM_TOKEN");
        EnvVarAccessPolicy policy = new EnvVarAccessPolicy(customKeys);
        
        ToolCall deniedCall = new ToolCall("command.exec", "run_command", 
            Map.of("command", "echo $MY_SECRET"));
        ToolContext context = new ToolContext(new TaskSummary(), "/workspace", null, 120);
        
        PolicyDecision deniedDecision = policy.evaluate(deniedCall, context);
        assertFalse(deniedDecision.isAllowed());
        
        // Default sensitive keys should not be blocked with custom set
        ToolCall allowedCall = new ToolCall("command.exec", "run_command", 
            Map.of("command", "echo $OPENAI_API_KEY"));
        PolicyDecision allowedDecision = policy.evaluate(allowedCall, context);
        assertTrue(allowedDecision.isAllowed());
    }

    @Test
    void envVarRestriction_AllowsEmptyCommand() {
        EnvVarAccessPolicy policy = new EnvVarAccessPolicy();
        ToolCall call = new ToolCall("command.exec", "run_command", 
            Map.of("command", ""));
        ToolContext context = new ToolContext(new TaskSummary(), "/workspace", null, 120);
        
        PolicyDecision decision = policy.evaluate(call, context);
        
        assertTrue(decision.isAllowed());
    }

    // ========================================
    // Network Access Restriction Tests
    // ========================================

    @Test
    void networkRestriction_DeniesNetworkCommandWhenDisabled() {
        NetworkAccessPolicy policy = new NetworkAccessPolicy(false);
        ToolCall call = new ToolCall("command.exec", "run_command", 
            Map.of("command", "curl https://example.com"));
        ToolContext context = new ToolContext(new TaskSummary(), "/workspace", null, 120);
        
        PolicyDecision decision = policy.evaluate(call, context);
        
        assertFalse(decision.isAllowed());
        assertEquals("network_not_allowed", decision.getReason());
    }

    @Test
    void networkRestriction_AllowsNetworkCommandWhenEnabled() {
        NetworkAccessPolicy policy = new NetworkAccessPolicy(true);
        ToolCall call = new ToolCall("command.exec", "run_command", 
            Map.of("command", "curl https://example.com"));
        ToolContext context = new ToolContext(new TaskSummary(), "/workspace", null, 120);
        
        PolicyDecision decision = policy.evaluate(call, context);
        
        assertTrue(decision.isAllowed());
    }

    @ParameterizedTest
    @ValueSource(strings = {
        "curl https://example.com",
        "wget http://example.com/file.txt",
        "ssh user@host",
        "scp file.txt user@host:/path",
        "git clone https://github.com/repo.git",
        "npm install package",
        "pip install requests",
        "invoke-webrequest https://example.com"
    })
    void networkRestriction_DeniesAllNetworkCommandsWhenDisabled(String command) {
        NetworkAccessPolicy policy = new NetworkAccessPolicy(false);
        ToolCall call = new ToolCall("command.exec", "run_command", 
            Map.of("command", command));
        ToolContext context = new ToolContext(new TaskSummary(), "/workspace", null, 120);
        
        PolicyDecision decision = policy.evaluate(call, context);
        
        assertFalse(decision.isAllowed());
        assertEquals("network_not_allowed", decision.getReason());
    }

    @Test
    void networkRestriction_AllowsNonNetworkCommands() {
        NetworkAccessPolicy policy = new NetworkAccessPolicy(false);
        ToolCall call = new ToolCall("command.exec", "run_command", 
            Map.of("command", "echo hello"));
        ToolContext context = new ToolContext(new TaskSummary(), "/workspace", null, 120);
        
        PolicyDecision decision = policy.evaluate(call, context);
        
        assertTrue(decision.isAllowed());
    }

    @Test
    void networkRestriction_IntegrationWithCommandSafetyPolicy() {
        CommandSafetyPolicy policy = new CommandSafetyPolicy(
            List.of("curl", "echo"), 
            false // Network disabled
        );
        
        // curl is in whitelist but network is disabled
        assertFalse(policy.isAllowed("curl https://example.com"));
        
        // echo is allowed and doesn't require network
        assertTrue(policy.isAllowed("echo test"));
    }

    // ========================================
    // Composite Policy Tests
    // ========================================

    @Test
    void compositePolicy_FirstDenyWins() {
        CompositeToolInvocationPolicy composite = CompositeToolInvocationPolicy.builder()
            .add(new ElevationDetectionPolicy())
            .add(new EnvVarAccessPolicy())
            .add(new NetworkAccessPolicy(false))
            .build();
        
        // Command violates elevation policy (first policy)
        ToolCall call = new ToolCall("command.exec", "run_command", 
            Map.of("command", "sudo curl https://example.com"));
        ToolContext context = new ToolContext(new TaskSummary(), "/workspace", null, 120);
        
        PolicyDecision decision = composite.evaluate(call, context);
        
        assertFalse(decision.isAllowed());
        assertEquals("elevation_not_allowed", decision.getReason());
    }

    @Test
    void compositePolicy_AllPoliciesMustPass() {
        CompositeToolInvocationPolicy composite = CompositeToolInvocationPolicy.builder()
            .add(new ElevationDetectionPolicy())
            .add(new EnvVarAccessPolicy())
            .add(new NetworkAccessPolicy(false))
            .build();
        
        // Command passes elevation and env checks but fails network check
        ToolCall call = new ToolCall("command.exec", "run_command", 
            Map.of("command", "curl https://example.com"));
        ToolContext context = new ToolContext(new TaskSummary(), "/workspace", null, 120);
        
        PolicyDecision decision = composite.evaluate(call, context);
        
        assertFalse(decision.isAllowed());
        assertEquals("network_not_allowed", decision.getReason());
    }

    @Test
    void compositePolicy_AllowsWhenAllPoliciesPass() {
        CompositeToolInvocationPolicy composite = CompositeToolInvocationPolicy.builder()
            .add(new ElevationDetectionPolicy())
            .add(new EnvVarAccessPolicy())
            .add(new NetworkAccessPolicy(true))
            .build();
        
        ToolCall call = new ToolCall("command.exec", "run_command", 
            Map.of("command", "echo hello"));
        ToolContext context = new ToolContext(new TaskSummary(), "/workspace", null, 120);
        
        PolicyDecision decision = composite.evaluate(call, context);
        
        assertTrue(decision.isAllowed());
    }

    // ========================================
    // Workspace Allowlist Policy Tests
    // ========================================

    @Test
    void workspaceAllowlist_AllowsWorkspaceInAllowlist() {
        WorkspaceAllowlistPolicy policy = new WorkspaceAllowlistPolicy(
            List.of("/allowed/workspace")
        );
        
        ToolCall call = new ToolCall("command.exec", "run_command", 
            Map.of("command", "echo test"));
        ToolContext context = new ToolContext(new TaskSummary(), "/allowed/workspace", null, 120);
        
        PolicyDecision decision = policy.evaluate(call, context);
        
        assertTrue(decision.isAllowed());
    }

    @Test
    void workspaceAllowlist_DeniesWorkspaceNotInAllowlist() {
        WorkspaceAllowlistPolicy policy = new WorkspaceAllowlistPolicy(
            List.of("/allowed/workspace")
        );
        
        ToolCall call = new ToolCall("command.exec", "run_command", 
            Map.of("command", "echo test"));
        ToolContext context = new ToolContext(new TaskSummary(), "/blocked/workspace", null, 120);
        
        PolicyDecision decision = policy.evaluate(call, context);
        
        assertFalse(decision.isAllowed());
        assertEquals("cwd_not_allowed", decision.getReason());
    }

    @Test
    void workspaceAllowlist_EmptyAllowlistAllowsAll() {
        WorkspaceAllowlistPolicy policy = new WorkspaceAllowlistPolicy(List.of());
        
        ToolCall call = new ToolCall("command.exec", "run_command", 
            Map.of("command", "echo test"));
        ToolContext context = new ToolContext(new TaskSummary(), "/any/workspace", null, 120);
        
        PolicyDecision decision = policy.evaluate(call, context);
        
        assertTrue(decision.isAllowed());
    }

    // ========================================
    // Security Policy Validator Tests
    // ========================================

    @Test
    void securityPolicyValidator_ReturnsAllRequiredPolicies() {
        Map<String, Object> policies = SecurityPolicyValidator.validateSecurityPolicies();
        
        assertNotNull(policies);
        assertTrue(policies.containsKey("commandWhitelisting"));
        assertTrue(policies.containsKey("privilegeEscalationPrevention"));
        assertTrue(policies.containsKey("sandboxIsolation"));
        assertTrue(policies.containsKey("resourceLimits"));
        assertTrue(policies.containsKey("overallStatus"));
    }

    @Test
    void securityPolicyValidator_CommandWhitelistingIsActive() {
        Map<String, Object> policies = SecurityPolicyValidator.validateSecurityPolicies();
        
        @SuppressWarnings("unchecked")
        Map<String, Object> commandWhitelisting = (Map<String, Object>) policies.get("commandWhitelisting");
        
        assertEquals("ACTIVE", commandWhitelisting.get("status"));
        assertTrue((Boolean) commandWhitelisting.get("configured"));
        assertNotNull(commandWhitelisting.get("description"));
    }

    @Test
    void securityPolicyValidator_PrivilegeEscalationPreventionIsActive() {
        Map<String, Object> policies = SecurityPolicyValidator.validateSecurityPolicies();
        
        @SuppressWarnings("unchecked")
        Map<String, Object> privilegePrevention = (Map<String, Object>) policies.get("privilegeEscalationPrevention");
        
        assertEquals("ACTIVE", privilegePrevention.get("status"));
        assertNotNull(privilegePrevention.get("measures"));
        String[] measures = (String[]) privilegePrevention.get("measures");
        assertTrue(measures.length >= 3);
    }

    @Test
    void securityPolicyValidator_OverallStatusIsSecure() {
        Map<String, Object> policies = SecurityPolicyValidator.validateSecurityPolicies();
        
        assertEquals("SECURE", policies.get("overallStatus"));
    }

    // ========================================
    // Helper Classes
    // ========================================

    private static SandboxExecuteRequest createRequest(String taskId, String command, Path workspace) {
        SandboxExecuteRequest request = new SandboxExecuteRequest();
        request.setTaskId(taskId);
        request.setCommand(command);
        request.setCwd(workspace.toString());
        request.setPrompt("run");
        request.setAssistant("python-agent");
        request.setSessionId("sess_test");
        return request;
    }

    private static final class RecordingAgentApiClient extends AgentApiClient {
        private final ArrayList<TaskEvent> events = new ArrayList<>();
        private final ArrayDeque<ApprovalDecision> decisions = new ArrayDeque<>();

        private RecordingAgentApiClient(ApprovalDecision... approvalDecisions) {
            super("http://localhost:8048", "test-token");
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
    }
}
