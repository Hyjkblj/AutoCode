FROM maven:3.9.9-eclipse-temurin-17 AS build
WORKDIR /build

# Copy shared-protocol first (dependency)
COPY shared-protocol/pom.xml shared-protocol/pom.xml
COPY shared-protocol/src shared-protocol/src

# Copy service
COPY artifact-service/pom.xml artifact-service/pom.xml
COPY artifact-service/src artifact-service/src

# Build shared-protocol first, then the service
RUN cd shared-protocol && mvn -q -DskipTests install && \
    cd ../artifact-service && mvn -q -DskipTests package

FROM eclipse-temurin:17-jdk-jammy
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /build/artifact-service/target/artifact-service-*.jar app.jar

EXPOSE 8081

HEALTHCHECK --interval=30s --timeout=3s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8081/actuator/health || exit 1

ENTRYPOINT ["java", "-jar", "app.jar"]
