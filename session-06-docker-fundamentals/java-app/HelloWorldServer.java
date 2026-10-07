import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;

/**
 * Minimal Hello World HTTP server using the JDK built-in HttpServer.
 * No external dependencies, so the Docker image stays small.
 */
public class HelloWorldServer {
    public static void main(String[] args) throws IOException {
        int port = Integer.parseInt(System.getenv().getOrDefault("PORT", "8080"));
        HttpServer server = HttpServer.create(new InetSocketAddress(port), 0);

        server.createContext("/", (HttpExchange exchange) -> {
            String host = InetAddress.getLocalHost().getHostName();
            String body = "<!DOCTYPE html>\n<html>\n  <head><title>Java Hello World</title></head>\n"
                    + "  <body style=\"font-family: sans-serif; text-align: center; margin-top: 80px;\">\n"
                    + "    <h1>Hello World from Java + Docker!</h1>\n"
                    + "    <p>Served by JDK HttpServer on container <b>" + host + "</b> (port " + port + ")</p>\n"
                    + "  </body>\n</html>\n";
            byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().add("Content-Type", "text/html; charset=utf-8");
            exchange.sendResponseHeaders(200, bytes.length);
            try (OutputStream os = exchange.getResponseBody()) {
                os.write(bytes);
            }
        });

        server.start();
        System.out.println("Java Hello World listening on port " + port);
    }
}
