FROM maven:3.9.9-eclipse-temurin-17 AS build
WORKDIR /build

COPY pom.xml .
COPY shared-protocol/pom.xml shared-protocol/pom.xml
COPY artifact-service/pom.xml artifact-service/pom.xml
COPY shared-protocol/src shared-protocol/src
COPY artifact-service/src artifact-service/src

RUN mvn -q -DskipTests -pl artifact-service -am package

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
