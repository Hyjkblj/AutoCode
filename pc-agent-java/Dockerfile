FROM maven:3.9.9-eclipse-temurin-17 AS build
WORKDIR /build

COPY pom.xml .
COPY shared-protocol/pom.xml shared-protocol/pom.xml
COPY pc-agent-java/pom.xml pc-agent-java/pom.xml
COPY shared-protocol/src shared-protocol/src
COPY pc-agent-java/src pc-agent-java/src

RUN mvn -q -DskipTests -pl pc-agent-java -am package

FROM eclipse-temurin:17-jre
WORKDIR /app

COPY --from=build /build/pc-agent-java/target/pc-agent-java-*-jar-with-dependencies.jar /app/pc-agent.jar

ENTRYPOINT ["java", "-jar", "/app/pc-agent.jar"]
