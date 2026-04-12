FROM maven:3.9.9-eclipse-temurin-17 AS build
WORKDIR /build

COPY pom.xml .
COPY shared-protocol/pom.xml shared-protocol/pom.xml
COPY control-plane-spring/pom.xml control-plane-spring/pom.xml
COPY pc-agent-java/pom.xml pc-agent-java/pom.xml
COPY shared-protocol/src shared-protocol/src
COPY control-plane-spring/src control-plane-spring/src

RUN mvn -q -DskipTests -pl control-plane-spring -am package

FROM eclipse-temurin:17-jre
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /app/data/artifacts /app/data/artifacts-hosted

COPY --from=build /build/control-plane-spring/target/control-plane-spring-*.jar /app/control-plane.jar

EXPOSE 8058
ENTRYPOINT ["java", "-jar", "/app/control-plane.jar"]
