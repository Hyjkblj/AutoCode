FROM maven:3.9.9-eclipse-temurin-17 AS build
WORKDIR /build

# Copy parent pom.xml (required by shared-protocol)
COPY pom.xml .

# Copy shared-protocol (dependency)
COPY shared-protocol/pom.xml shared-protocol/pom.xml
COPY shared-protocol/src shared-protocol/src

# Copy service
COPY event-service/pom.xml event-service/pom.xml
COPY event-service/src event-service/src

# Build shared-protocol first, then the service
RUN cd shared-protocol && mvn -q -DskipTests install && \
    cd ../event-service && mvn -q -DskipTests package

FROM eclipse-temurin:17-jdk-jammy
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /build/event-service/target/event-service-*.jar app.jar

EXPOSE 8082

HEALTHCHECK --interval=30s --timeout=3s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8082/actuator/health || exit 1

ENTRYPOINT ["java", "-jar", "app.jar"]
