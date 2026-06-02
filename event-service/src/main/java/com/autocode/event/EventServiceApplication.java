package com.autocode.event;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * Event Service — standalone Spring Boot microservice.
 *
 * Responsibilities (Requirements 11.1, 2.4, 2.5):
 *  - Process events with explicit ACK protocol (2.4)
 *  - Implement Redis-based event deduplication (2.5)
 *  - Maintain event sequence continuity (2.6)
 *  - Provide clear service boundaries and data ownership (11.1)
 *
 * This service runs independently of the Control Plane on port 8082.
 */
@SpringBootApplication
public class EventServiceApplication {

    public static void main(String[] args) {
        SpringApplication.run(EventServiceApplication.class, args);
    }
}
