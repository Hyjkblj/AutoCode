FROM maven:3.9.9-eclipse-temurin-17 AS build
WORKDIR /build

# Copy shared-protocol first (dependency)
COPY shared-protocol/pom.xml shared-protocol/pom.xml
COPY shared-protocol/src shared-protocol/src

# Copy service
COPY approval-service/pom.xml approval-service/pom.xml
COPY approval-service/src approval-service/src

# Build shared-protocol first, then the service
RUN cd shared-protocol && mvn -q -DskipTests install && \
    cd ../approval-service && mvn -q -DskipTests package

FROM eclipse-temurin:17-jdk-jammy
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /build/approval-service/target/approval-service-*.jar app.jar

EXPOSE 8064

HEALTHCHECK --interval=30s --timeout=3s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8064/actuator/health || exit 1

ENTRYPOINT ["java", "-jar", "app.jar"]
