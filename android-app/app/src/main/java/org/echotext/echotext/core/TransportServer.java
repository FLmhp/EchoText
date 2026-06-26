package org.echotext.echotext.core;

import java.io.BufferedInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.BindException;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

import org.echotext.echotext.model.DeviceIdentity;
import org.echotext.echotext.model.Peer;
import org.echotext.echotext.model.TextMessage;
import org.json.JSONException;
import org.json.JSONObject;

public class TransportServer {
    public static final int DEFAULT_PORT = 48735;

    public interface IdentityProvider {
        DeviceIdentity identity() throws Exception;
    }

    public interface PairCodeMatcher {
        boolean matches(String code);
    }

    public interface PeerProvider {
        Peer peer(String deviceId);
    }

    public interface MessageHandler {
        void onMessage(TextMessage message, Peer peer);
    }

    public interface PairHandler {
        void onPeerPaired(Peer peer);
    }

    private final IdentityProvider identityProvider;
    private final PairCodeMatcher pairCodeMatcher;
    private final PeerProvider peerProvider;
    private final MessageHandler messageHandler;
    private final PairHandler pairHandler;
    private final ExecutorService executor = Executors.newCachedThreadPool();
    private final AtomicBoolean running = new AtomicBoolean(false);

    private ServerSocket serverSocket;

    public TransportServer(
            IdentityProvider identityProvider,
            PairCodeMatcher pairCodeMatcher,
            PeerProvider peerProvider,
            MessageHandler messageHandler,
            PairHandler pairHandler) {
        this.identityProvider = identityProvider;
        this.pairCodeMatcher = pairCodeMatcher;
        this.peerProvider = peerProvider;
        this.messageHandler = messageHandler;
        this.pairHandler = pairHandler;
    }

    public void start() throws IOException {
        if (!running.compareAndSet(false, true)) {
            return;
        }
        try {
            serverSocket = new ServerSocket(DEFAULT_PORT);
        } catch (BindException exception) {
            serverSocket = new ServerSocket(0);
        }
        executor.execute(this::acceptLoop);
    }

    public void stop() {
        running.set(false);
        if (serverSocket != null) {
            try {
                serverSocket.close();
            } catch (IOException ignored) {
                // Ignore shutdown races.
            }
        }
        executor.shutdownNow();
    }

    public int getPort() {
        return serverSocket == null ? 0 : serverSocket.getLocalPort();
    }

    private void acceptLoop() {
        while (running.get()) {
            try {
                Socket socket = serverSocket.accept();
                executor.execute(() -> handle(socket));
            } catch (IOException ignored) {
                // Exit when closed.
            }
        }
    }

    private void handle(Socket socket) {
        try (socket; BufferedInputStream input = new BufferedInputStream(socket.getInputStream());
             OutputStream output = socket.getOutputStream()) {
            String requestLine = readLine(input);
            if (requestLine == null || requestLine.trim().isEmpty()) {
                return;
            }
            String[] requestParts = requestLine.split(" ");
            if (requestParts.length < 2) {
                writeJson(output, 400, new JSONObject().put("error", "bad_request"));
                return;
            }
            String method = requestParts[0];
            String path = requestParts[1];
            Map<String, String> headers = readHeaders(input);
            byte[] body = readBody(input, headers);
            route(method, path, headers, body, output);
        } catch (Exception ignored) {
            // Best-effort request handling.
        }
    }

    private void route(String method, String path, Map<String, String> headers, byte[] body, OutputStream output)
            throws Exception {
        if ("GET".equals(method) && "/api/v1/hello".equals(path)) {
            JSONObject payload = new JSONObject();
            payload.put("device", identityProvider.identity().toJson());
            writeJson(output, 200, payload);
            return;
        }
        if (!"POST".equals(method)) {
            writeJson(output, 404, new JSONObject().put("error", "not_found"));
            return;
        }

        JSONObject payload;
        try {
            payload = new JSONObject(new String(body, StandardCharsets.UTF_8));
        } catch (JSONException exception) {
            writeJson(output, 400, new JSONObject().put("error", "invalid_json"));
            return;
        }

        if ("/api/v1/pair".equals(path)) {
            handlePair(payload, output);
            return;
        }
        if ("/api/v1/messages".equals(path)) {
            handleMessage(payload, headers, output);
            return;
        }
        writeJson(output, 404, new JSONObject().put("error", "not_found"));
    }

    private void handlePair(JSONObject payload, OutputStream output) throws Exception {
        try {
            DeviceIdentity identity = DeviceIdentity.fromJson(payload.getJSONObject("device"));
            String pairCode = payload.getString("pair_code");
            String sharedSecret = payload.getString("shared_secret");
            if (!pairCodeMatcher.matches(pairCode)) {
                writeJson(output, 403, new JSONObject().put("error", "pair_code_rejected"));
                return;
            }
            Peer peer = new Peer(
                    identity.deviceId,
                    identity.name,
                    identity.platform,
                    identity.host,
                    identity.port,
                    System.currentTimeMillis() / 1000.0,
                    sharedSecret);
            pairHandler.onPeerPaired(peer);
            JSONObject response = new JSONObject();
            response.put("ok", true);
            response.put("device", identityProvider.identity().toJson());
            writeJson(output, 200, response);
        } catch (JSONException exception) {
            writeJson(output, 400, new JSONObject().put("error", "invalid_pair_payload"));
        }
    }

    private void handleMessage(JSONObject payload, Map<String, String> headers, OutputStream output)
            throws Exception {
        try {
            TextMessage message = TextMessage.fromJson(payload.getJSONObject("message"));
            Peer peer = peerProvider.peer(message.senderId);
            if (peer == null || peer.sharedSecret == null) {
                writeJson(output, 403, new JSONObject().put("error", "peer_not_paired"));
                return;
            }
            String signature = headers.getOrDefault("x-echotext-signature", "");
            if (!SecurityUtils.verifySignature(peer.sharedSecret, payload, signature)) {
                writeJson(output, 403, new JSONObject().put("error", "invalid_signature"));
                return;
            }
            messageHandler.onMessage(message, peer);
            writeJson(output, 200, new JSONObject().put("ok", true));
        } catch (JSONException exception) {
            writeJson(output, 400, new JSONObject().put("error", "invalid_message_payload"));
        } catch (GeneralSecurityException exception) {
            writeJson(output, 403, new JSONObject().put("error", "invalid_signature"));
        }
    }

    private static Map<String, String> readHeaders(InputStream input) throws IOException {
        Map<String, String> headers = new HashMap<>();
        while (true) {
            String line = readLine(input);
            if (line == null || line.isEmpty()) {
                break;
            }
            int separator = line.indexOf(':');
            if (separator > 0) {
                String name = line.substring(0, separator).trim().toLowerCase();
                String value = line.substring(separator + 1).trim();
                headers.put(name, value);
            }
        }
        return headers;
    }

    private static byte[] readBody(InputStream input, Map<String, String> headers) throws IOException {
        int contentLength = Integer.parseInt(headers.getOrDefault("content-length", "0"));
        byte[] body = new byte[contentLength];
        int offset = 0;
        while (offset < contentLength) {
            int read = input.read(body, offset, contentLength - offset);
            if (read == -1) {
                break;
            }
            offset += read;
        }
        return body;
    }

    private static String readLine(InputStream input) throws IOException {
        ByteArrayOutputStream buffer = new ByteArrayOutputStream();
        int previous = -1;
        while (true) {
            int current = input.read();
            if (current == -1) {
                if (buffer.size() == 0) {
                    return null;
                }
                break;
            }
            if (previous == '\r' && current == '\n') {
                break;
            }
            if (previous != -1) {
                buffer.write(previous);
            }
            previous = current;
        }
        return new String(buffer.toByteArray(), StandardCharsets.UTF_8);
    }

    private static void writeJson(OutputStream output, int status, JSONObject payload) throws IOException {
        byte[] body = payload.toString().getBytes(StandardCharsets.UTF_8);
        String reason = switch (status) {
            case 200 -> "OK";
            case 400 -> "Bad Request";
            case 403 -> "Forbidden";
            case 404 -> "Not Found";
            default -> "OK";
        };
        String headers =
                "HTTP/1.1 " + status + " " + reason + "\r\n"
                        + "Content-Type: application/json; charset=utf-8\r\n"
                        + "Content-Length: " + body.length + "\r\n"
                        + "Connection: close\r\n"
                        + "\r\n";
        output.write(headers.getBytes(StandardCharsets.UTF_8));
        output.write(body);
        output.flush();
    }
}
