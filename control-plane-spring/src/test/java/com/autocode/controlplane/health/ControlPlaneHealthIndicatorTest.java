package com.autocode.controlplane.health;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.boot.actuate.health.Health;
import org.springframework.boot.actuate.health.Status;
import org.springframework.data.redis.connection.RedisConnection;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.data.redis.core.RedisTemplate;

import javax.sql.DataSource;
import java.sql.Connection;
import java.sql.SQLException;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class ControlPlaneHealthIndicatorTest {

    @Mock
    private DataSource dataSource;

    @Mock
    private RedisTemplate<String, Object> redisTemplate;

    @Mock
    private Connection sqlConnection;

    @Mock
    private RedisConnectionFactory redisConnectionFactory;

    @Mock
    private RedisConnection redisConnection;

    private ControlPlaneHealthIndicator healthIndicator;

    @BeforeEach
    void setUp() {
        healthIndicator = new ControlPlaneHealthIndicator(dataSource, redisTemplate);
    }

    @Test
    void health_WhenAllDependenciesHealthy_ReturnsUp() throws SQLException {
        // Arrange
        when(dataSource.getConnection()).thenReturn(sqlConnection);
        when(sqlConnection.isValid(1)).thenReturn(true);
        
        when(redisTemplate.getConnectionFactory()).thenReturn(redisConnectionFactory);
        when(redisConnectionFactory.getConnection()).thenReturn(redisConnection);
        when(redisConnection.ping()).thenReturn("PONG");

        // Act
        Health health = healthIndicator.health();

        // Assert
        assertEquals(Status.UP, health.getStatus());
        assertEquals("UP", health.getDetails().get("database"));
        assertEquals("UP", health.getDetails().get("redis"));
        assertEquals(8058, health.getDetails().get("port"));
        assertTrue((Long) health.getDetails().get("responseTimeMs") < 2000);
    }

    @Test
    void health_WhenDatabaseDown_ReturnsDown() throws SQLException {
        // Arrange
        when(dataSource.getConnection()).thenReturn(sqlConnection);
        when(sqlConnection.isValid(1)).thenReturn(false);
        
        when(redisTemplate.getConnectionFactory()).thenReturn(redisConnectionFactory);
        when(redisConnectionFactory.getConnection()).thenReturn(redisConnection);
        when(redisConnection.ping()).thenReturn("PONG");

        // Act
        Health health = healthIndicator.health();

        // Assert
        assertEquals(Status.DOWN, health.getStatus());
        assertEquals("DOWN", health.getDetails().get("database"));
        assertEquals("UP", health.getDetails().get("redis"));
    }

    @Test
    void health_WhenRedisDown_ReturnsDown() throws SQLException {
        // Arrange
        when(dataSource.getConnection()).thenReturn(sqlConnection);
        when(sqlConnection.isValid(1)).thenReturn(true);
        
        when(redisTemplate.getConnectionFactory()).thenReturn(redisConnectionFactory);
        when(redisConnectionFactory.getConnection()).thenThrow(new RuntimeException("Redis connection failed"));

        // Act
        Health health = healthIndicator.health();

        // Assert
        assertEquals(Status.DOWN, health.getStatus());
        assertEquals("UP", health.getDetails().get("database"));
        assertEquals("DOWN", health.getDetails().get("redis"));
    }

    @Test
    void health_WhenExceptionThrown_ReturnsDown() throws SQLException {
        // Arrange
        when(dataSource.getConnection()).thenThrow(new SQLException("Database connection failed"));

        // Act
        Health health = healthIndicator.health();

        // Assert
        assertEquals(Status.DOWN, health.getStatus());
        assertTrue(health.getDetails().containsKey("error"));
        assertEquals(8058, health.getDetails().get("port"));
    }
}