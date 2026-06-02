FROM openjdk:17-jdk-slim

WORKDIR /app

# Copy the JAR file
COPY target/approval-service-*.jar app.jar

# Expose the port
EXPOSE 8064

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8064/actuator/health || exit 1

# Run the application
ENTRYPOINT ["java", "-jar", "app.jar"]