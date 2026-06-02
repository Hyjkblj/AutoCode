package com.autocode.artifact;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.actuate.health.Health;
import org.springframework.boot.actuate.health.HealthIndicator;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

/**
 * Health indicator that checks connectivity to the Control Plane.
 *
 * <p>Satisfies Requirement 11.2: service-to-service communication with proper
 * error handling and health checks for service dependencies.
 *
 * <p>Disabled by default in test profiles via
 * {@code artifact-service.control-plane.health-check.enabled=false}.
 */
@Component
@ConditionalOnProperty(
        name = "artifact-service.control-plane.health-check.enabled",
        havingValue = "true",
        matchIfMissing = true
)
public class ControlPlaneHealthIndicator implements HealthIndicator {

    private static final Logger log = LoggerFactory.getLogger(ControlPlaneHealthIndicator.class);

    private final String controlPlaneUrl;
    private final RestTemplate restTemplate;

    public ControlPlaneHealthIndicator(
            @Value("${artifact-service.control-plane.url:http://localhost:8058}") String controlPlaneUrl
    ) {
        this.controlPlaneUrl = controlPlaneUrl;
        this.restTemplate = new RestTemplate();
    }

    @Override
    public Health health() {
        String healthUrl = controlPlaneUrl + "/actuator/health";
        try {
            restTemplate.getForObject(healthUrl, String.class);
            return Health.up()
                    .withDetail("controlPlaneUrl", controlPlaneUrl)
                    .withDetail("status", "reachable")
                    .build();
        } catch (Exception ex) {
            log.warn("Control Plane health check failed: url={} error={}", healthUrl, ex.getMessage());
            return Health.down()
                    .withDetail("controlPlaneUrl", controlPlaneUrl)
                    .withDetail("error", ex.getMessage())
                    .build();
        }
    }
}
