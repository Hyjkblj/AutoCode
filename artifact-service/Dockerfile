FROM eclipse-temurin:17-jdk-jammy

WORKDIR /app

# Copy the JAR file
COPY target/artifact-service-*.jar app.jar

# Expose the port
EXPOSE 8081

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8081/actuator/health || exit 1

# Run the application
ENTRYPOINT ["java", "-jar", "app.jar"]
