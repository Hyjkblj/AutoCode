FROM eclipse-temurin:17-jdk-jammy

WORKDIR /app

# Copy the built JAR file
COPY target/gateway-service-*.jar app.jar

# Expose the gateway port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8080/healthz || exit 1

# Run the application
ENTRYPOINT ["java", "-jar", "app.jar"]