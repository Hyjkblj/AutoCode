package com.autocode.gateway.health;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.actuate.health.Health;
import org.springframework.boot.actuate.health.HealthIndicator;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.time.Duration;
import java.time.Instant;
import java.util.HashMap;
import java.util.Map;

/**
 * Custom health indicator for Spring Cloud Gateway.
 * Checks upstream service availability and routing configuration.
 */
@Component
public class GatewayHealthIndicator implements HealthIndicator {

    private final WebClient webClient;
    
    @Value("${gateway.upstream.control-plane.url:http://localhost:8058}")
    private String controlPlaneUrl;
    
    @Value("${gateway.upstream.java-sandbox.url:http://localhost:18080}")
    private String javaSandboxUrl;

    public GatewayHealthIndicator() {
        this.webClient = WebClient.builder()
            .codecs(configurer -> configurer.defaultCodecs().maxInMemorySize(1024 * 1024))
            .build();
    }

    @Override
    public Health health() {
        try {
            Instant startTime = Instant.now();
            
            // Check upstream services
            Map<String, Object> upstreamStatus = checkUpstreamServices();
            
            // Check routing configuration
            boolean routingConfigured = checkRoutingConfiguration();
            
            // Check response time
            Duration responseTime = Duration.between(startTime, Instant.now());
            boolean responseTimeOk = responseTime.toMillis() < 2000;
            
            boolean allHealthy = (boolean) upstreamStatus.get("controlPlaneHealthy") &&
                               (boolean) upstreamStatus.get("javaSandboxHealthy") &&
                               routingConfigured &&
                               responseTimeOk;
            
            Health.Builder builder = allHealthy ? Health.up() : Health.down();
            
            return builder
                .withDetail("port", 8080)
                .withDetail("responseTimeMs", responseTime.toMillis())
                .withDetail("routingConfigured", routingConfigured)
                .withDetail("upstreamServices", upstreamStatus)
                .withDetail("features", Map.of(
                    "traceIdPropagation", true,
                    "authHeaderPropagation", true,
                    "timeoutPolicies", true,
                    "rateLimiting", true
                ))
                .build();
                
        } catch (Exception e) {
            return Health.down()
                .withDetail("error", e.getMessage())
                .withDetail("port", 8080)
                .build();
        }
    }

    private Map<String, Object> checkUpstreamServices() {
        Map<String, Object> status = new HashMap<>();
        
        // Check Control Plane
        try {
            String controlPlaneHealth = webClient.get()
                .uri(controlPlaneUrl + "/actuator/health")
                .retrieve()
                .bodyToMono(String.class)
                .timeout(Duration.ofSeconds(2))
                .block();
            
            status.put("controlPlaneHealthy", controlPlaneHealth != null && controlPlaneHealth.contains("UP"));
            status.put("controlPlaneUrl", controlPlaneUrl);
        } catch (Exception e) {
            status.put("controlPlaneHealthy", false);
            status.put("controlPlaneError", e.getMessage());
        }
        
        // Check Java Sandbox
        try {
            String sandboxHealth = webClient.get()
                .uri(javaSandboxUrl + "/sandbox/health")
                .retrieve()
                .bodyToMono(String.class)
                .timeout(Duration.ofSeconds(2))
                .block();
            
            status.put("javaSandboxHealthy", sandboxHealth != null && sandboxHealth.contains("\"ok\":true"));
            status.put("javaSandboxUrl", javaSandboxUrl);
        } catch (Exception e) {
            status.put("javaSandboxHealthy", false);
            status.put("javaSandboxError", e.getMessage());
        }
        
        return status;
    }

    private boolean checkRoutingConfiguration() {
        // In a real implementation, this would validate that routing rules are properly loaded
        // For now, we'll assume routing is configured if the application started successfully
        return true;
    }
}