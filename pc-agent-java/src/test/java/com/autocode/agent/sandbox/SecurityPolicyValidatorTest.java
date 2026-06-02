package com.autocode.agent.sandbox;

import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

class SecurityPolicyValidatorTest {

    @Test
    void validateSecurityPolicies_ReturnsAllPolicyChecks() {
        // Act
        Map<String, Object> policies = SecurityPolicyValidator.validateSecurityPolicies();

        // Assert
        assertNotNull(policies);
        assertTrue(policies.containsKey("commandWhitelisting"));
        assertTrue(policies.containsKey("privilegeEscalationPrevention"));
        assertTrue(policies.containsKey("sandboxIsolation"));
        assertTrue(policies.containsKey("resourceLimits"));
        assertTrue(policies.containsKey("overallStatus"));
    }

    @Test
    void validateSecurityPolicies_CommandWhitelistingHasCorrectStructure() {
        // Act
        Map<String, Object> policies = SecurityPolicyValidator.validateSecurityPolicies();

        // Assert
        @SuppressWarnings("unchecked")
        Map<String, Object> commandWhitelisting = (Map<String, Object>) policies.get("commandWhitelisting");
        
        assertNotNull(commandWhitelisting);
        assertTrue(commandWhitelisting.containsKey("status"));
        assertTrue(commandWhitelisting.containsKey("description"));
        assertTrue(commandWhitelisting.containsKey("configured"));
        
        assertEquals("ACTIVE", commandWhitelisting.get("status"));
        assertTrue((Boolean) commandWhitelisting.get("configured"));
    }

    @Test
    void validateSecurityPolicies_PrivilegeEscalationPreventionHasCorrectStructure() {
        // Act
        Map<String, Object> policies = SecurityPolicyValidator.validateSecurityPolicies();

        // Assert
        @SuppressWarnings("unchecked")
        Map<String, Object> privilegePrevention = (Map<String, Object>) policies.get("privilegeEscalationPrevention");
        
        assertNotNull(privilegePrevention);
        assertTrue(privilegePrevention.containsKey("status"));
        assertTrue(privilegePrevention.containsKey("description"));
        assertTrue(privilegePrevention.containsKey("measures"));
        
        assertEquals("ACTIVE", privilegePrevention.get("status"));
        
        String[] measures = (String[]) privilegePrevention.get("measures");
        assertEquals(3, measures.length);
        assertEquals("User context isolation", measures[0]);
    }

    @Test
    void validateSecurityPolicies_SandboxIsolationHasCorrectStructure() {
        // Act
        Map<String, Object> policies = SecurityPolicyValidator.validateSecurityPolicies();

        // Assert
        @SuppressWarnings("unchecked")
        Map<String, Object> sandboxIsolation = (Map<String, Object>) policies.get("sandboxIsolation");
        
        assertNotNull(sandboxIsolation);
        assertTrue(sandboxIsolation.containsKey("status"));
        assertTrue(sandboxIsolation.containsKey("description"));
        assertTrue(sandboxIsolation.containsKey("features"));
        
        assertEquals("ACTIVE", sandboxIsolation.get("status"));
        
        String[] features = (String[]) sandboxIsolation.get("features");
        assertEquals(3, features.length);
    }

    @Test
    void validateSecurityPolicies_ResourceLimitsHasCorrectStructure() {
        // Act
        Map<String, Object> policies = SecurityPolicyValidator.validateSecurityPolicies();

        // Assert
        @SuppressWarnings("unchecked")
        Map<String, Object> resourceLimits = (Map<String, Object>) policies.get("resourceLimits");
        
        assertNotNull(resourceLimits);
        assertTrue(resourceLimits.containsKey("status"));
        assertTrue(resourceLimits.containsKey("description"));
        assertTrue(resourceLimits.containsKey("limits"));
        
        assertEquals("ACTIVE", resourceLimits.get("status"));
        
        @SuppressWarnings("unchecked")
        Map<String, Object> limits = (Map<String, Object>) resourceLimits.get("limits");
        assertEquals(512, limits.get("maxMemoryMB"));
        assertEquals(300, limits.get("maxExecutionTimeSeconds"));
        assertEquals("10MB", limits.get("maxFileSize"));
    }

    @Test
    void validateSecurityPolicies_OverallStatusIsSecureWhenAllPoliciesActive() {
        // Act
        Map<String, Object> policies = SecurityPolicyValidator.validateSecurityPolicies();

        // Assert
        assertEquals("SECURE", policies.get("overallStatus"));
    }
}