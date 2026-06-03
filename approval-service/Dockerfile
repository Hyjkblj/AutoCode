FROM maven:3.9.9-eclipse-temurin-17 AS build
WORKDIR /build

# Copy parent pom.xml
COPY pom.xml .

# Create all module directories (required by Maven parent pom)
RUN mkdir -p shared-protocol/src \
    control-plane-spring/src \
    pc-agent-java/src \
    gateway-service/src \
    approval-service/src \
    artifact-service/src \
    event-service/src

# Copy all module pom.xml files
COPY shared-protocol/pom.xml shared-protocol/pom.xml
COPY control-plane-spring/pom.xml control-plane-spring/pom.xml
COPY pc-agent-java/pom.xml pc-agent-java/pom.xml
COPY gateway-service/pom.xml gateway-service/pom.xml
COPY approval-service/pom.xml approval-service/pom.xml
COPY artifact-service/pom.xml artifact-service/pom.xml
COPY event-service/pom.xml event-service/pom.xml

# Copy source code for dependencies and target service
COPY shared-protocol/src shared-protocol/src
COPY approval-service/src approval-service/src

# Build using Maven multi-module approach
RUN mvn -q -DskipTests -pl approval-service -am package

FROM eclipse-temurin:17-jre
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /build/approval-service/target/approval-service-*.jar app.jar

EXPOSE 8064

HEALTHCHECK --interval=30s --timeout=3s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8064/actuator/health || exit 1

ENTRYPOINT ["java", "-jar", "app.jar"]
