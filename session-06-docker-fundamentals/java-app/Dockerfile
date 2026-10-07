# Java Hello World - multi-stage Dockerfile
# Stage 1: compile with the JDK
FROM eclipse-temurin:21-jdk-alpine AS build
WORKDIR /src
COPY HelloWorldServer.java .
RUN javac HelloWorldServer.java

# Stage 2: run with the smaller JRE image
FROM eclipse-temurin:21-jre-alpine
WORKDIR /app
COPY --from=build /src/HelloWorldServer.class .
EXPOSE 8080
CMD ["java", "HelloWorldServer"]
