FROM maven:3.9.9-eclipse-temurin-17 AS build
WORKDIR /build

# Copy Maven settings with Aliyun mirror for faster downloads
COPY .mvn/settings.xml /root/.m2/settings.xml

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
COPY pc-agent-java/src pc-agent-java/src

# Build using Maven multi-module approach (skip test compilation entirely)
RUN mvn -q -Dmaven.test.skip=true -pl pc-agent-java -am package

FROM eclipse-temurin:17-jre
WORKDIR /app

COPY --from=build /build/pc-agent-java/target/pc-agent-java-*-jar-with-dependencies.jar /app/pc-agent.jar

ENTRYPOINT ["java", "-jar", "/app/pc-agent.jar"]
