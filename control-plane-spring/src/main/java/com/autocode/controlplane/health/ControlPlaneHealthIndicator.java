package com.autocode.controlplane.health;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.actuate.health.Health;
import org.springframework.boot.actuate.health.HealthIndicator;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Component;

import javax.sql.DataSource;
import java.sql.Connection;
import java.sql.SQLException;
import java.time.Duration;
import java.time.Instant;

/**
 * Custom health indicator for Control Plane that checks critical dependencies.
 * Validates database connectivity, Redis availability, and system readiness.
 */
@Component
public class ControlPlaneHealthIndicator implements HealthIndicator {

    private final DataSource dataSource;
    private final RedisTemplate<String, Object> redisTemplate;

    @Autowired
    public ControlPlaneHealthIndicator(DataSource dataSource, RedisTemplate<String, Object> redisTemplate) {
        this.dataSource = dataSource;
        this.redisTemplate = redisTemplate;
    }

    @Override
    public Health health() {
        Health.Builder builder = new Health.Builder();
        
        try {
            Instant startTime = Instant.now();
            
            // Check database connectivity
            boolean dbHealthy = checkDatabaseHealth();
            
            // Check Redis connectivity
            boolean redisHealthy = checkRedisHealth();
            
            // Check response time requirement (< 2 seconds)
            Duration responseTime = Duration.between(startTime, Instant.now());
            boolean responseTimeOk = responseTime.toMillis() < 2000;
            
            if (dbHealthy && redisHealthy && responseTimeOk) {
                builder.up()
                    .withDetail("database", "UP")
                    .withDetail("redis", "UP")
                    .withDetail("responseTimeMs", responseTime.toMillis())
                    .withDetail("port", 8058)
                    .withDetail("dependencies", "All dependencies healthy");
            } else {
                builder.down()
                    .withDetail("database", dbHealthy ? "UP" : "DOWN")
                    .withDetail("redis", redisHealthy ? "UP" : "DOWN")
                    .withDetail("responseTimeMs", responseTime.toMillis())
                    .withDetail("responseTimeOk", responseTimeOk)
                    .withDetail("port", 8058);
            }
            
        } catch (Exception e) {
            builder.down()
                .withDetail("error", e.getMessage())
                .withDetail("port", 8058);
        }
        
        return builder.build();
    }

    private boolean checkDatabaseHealth() {
        try (Connection connection = dataSource.getConnection()) {
            return connection.isValid(1); // 1 second timeout
        } catch (SQLException e) {
            return false;
        }
    }

    private boolean checkRedisHealth() {
        try {
            // Simple ping to Redis
            String result = redisTemplate.getConnectionFactory()
                .getConnection()
                .ping();
            return "PONG".equals(result);
        } catch (Exception e) {
            return false;
        }
    }
}