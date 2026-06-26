package org.echotext.echotext.core;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.util.Collections;
import java.util.HashMap;
import java.util.Map;

import org.echotext.echotext.model.DeviceIdentity;
import org.echotext.echotext.model.Peer;
import org.echotext.echotext.model.TextMessage;
import org.json.JSONException;
import org.json.JSONObject;

public class TransportClient {
    public DeviceIdentity pair(Peer peer, DeviceIdentity identity, String pairCode, String sharedSecret)
            throws IOException, JSONException {
        JSONObject payload = new JSONObject();
        payload.put("device", identity.toJson());
        payload.put("pair_code", pairCode);
        payload.put("shared_secret", sharedSecret);
        JSONObject response = post(peer, "/api/v1/pair", payload, Collections.emptyMap());
        return DeviceIdentity.fromJson(response.getJSONObject("device"));
    }

    public void sendMessage(Peer peer, TextMessage message)
            throws IOException, JSONException, GeneralSecurityException {
        if (peer.sharedSecret == null) {
            throw new IOException("Peer is not paired");
        }
        JSONObject payload = new JSONObject();
        payload.put("message", message.toJson());
        String signature = SecurityUtils.signPayload(peer.sharedSecret, payload);
        Map<String, String> headers = new HashMap<>();
        headers.put("X-EchoText-Signature", signature);
        post(peer, "/api/v1/messages", payload, headers);
    }

    private JSONObject post(Peer peer, String path, JSONObject payload, Map<String, String> headers)
            throws IOException, JSONException {
        URL url = new URL("http://" + peer.host + ":" + peer.port + path);
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        connection.setConnectTimeout(5_000);
        connection.setReadTimeout(5_000);
        connection.setRequestMethod("POST");
        connection.setDoOutput(true);
        connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
        for (Map.Entry<String, String> entry : headers.entrySet()) {
            connection.setRequestProperty(entry.getKey(), entry.getValue());
        }
        byte[] body = payload.toString().getBytes(StandardCharsets.UTF_8);
        try (OutputStream outputStream = connection.getOutputStream()) {
            outputStream.write(body);
        }
        int status = connection.getResponseCode();
        InputStream stream = status >= 400 ? connection.getErrorStream() : connection.getInputStream();
        String response = "";
        if (stream != null) {
            response = readUtf8(stream);
            stream.close();
        }
        if (status >= 400) {
            throw new IOException("Peer returned HTTP " + status + ": " + response);
        }
        return new JSONObject(response);
    }

    private static String readUtf8(InputStream stream) throws IOException {
        ByteArrayOutputStream buffer = new ByteArrayOutputStream();
        byte[] chunk = new byte[4096];
        int read;
        while ((read = stream.read(chunk)) != -1) {
            buffer.write(chunk, 0, read);
        }
        return new String(buffer.toByteArray(), StandardCharsets.UTF_8);
    }
}
