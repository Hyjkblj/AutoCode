package com.autocode.artifact;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * Artifact Service — standalone Spring Boot microservice.
 *
 * Responsibilities (Requirements 11.1, 11.2, 14.x):
 *  - Store generated code artifacts with unique identifiers (14.1)
 *  - Provide HTTP access with proper content-type headers (14.2)
 *  - Serve downloadable ZIP packages (14.3)
 *  - Maintain artifact metadata including generation timestamp (14.4)
 *  - Enforce retention policies (14.5)
 *  - Log access events for audit purposes (14.6)
 *
 * This service runs independently of the Control Plane on port 8081.
 */
@SpringBootApplication
public class ArtifactServiceApplication {

    public static void main(String[] args) {
        SpringApplication.run(ArtifactServiceApplication.class, args);
    }
}
