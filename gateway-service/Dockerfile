FROM maven:3.9.9-eclipse-temurin-17 AS build
WORKDIR /build

COPY pom.xml .
COPY shared-protocol/pom.xml shared-protocol/pom.xml
COPY control-plane-spring/pom.xml control-plane-spring/pom.xml
COPY pc-agent-java/pom.xml pc-agent-java/pom.xml
COPY gateway-service/pom.xml gateway-service/pom.xml
COPY shared-protocol/src shared-protocol/src
COPY gateway-service/src gateway-service/src

RUN mvn -q -DskipTests -pl gateway-service -am package

FROM eclipse-temurin:17-jdk-jammy
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /build/gateway-service/target/gateway-service-*.jar app.jar

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8080/actuator/health || exit 1

ENTRYPOINT ["java", "-jar", "app.jar"]
