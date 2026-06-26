package org.echotext.echotext.core;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.ConnectException;
import java.net.HttpURLConnection;
import java.net.NoRouteToHostException;
import java.net.SocketTimeoutException;
import java.net.UnknownHostException;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.util.Collections;
import java.util.HashMap;
import java.util.Map;

import android.util.Log;

import org.echotext.echotext.model.DeviceIdentity;
import org.echotext.echotext.model.Peer;
import org.echotext.echotext.model.TextMessage;
import org.json.JSONException;
import org.json.JSONObject;

public class TransportClient {
    private static final String TAG = "EchoTextTransport";

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
        Log.i(TAG, "POST " + path + " -> " + peer.host + ":" + peer.port);
        HttpURLConnection connection = null;
        try {
            connection = (HttpURLConnection) url.openConnection();
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
                TransportFailure failure = mapHttpFailure(status, response);
                Log.w(TAG, "HTTP failure " + failure.kind + " status=" + status + " body=" + response);
                throw failure;
            }
            return new JSONObject(response);
        } catch (SocketTimeoutException exception) {
            Log.w(TAG, "POST timed out for " + peer.host + ":" + peer.port, exception);
            throw new TransportFailure(TransportFailure.Kind.CONNECTION_TIMEOUT, exception.getMessage(), exception);
        } catch (ConnectException exception) {
            Log.w(TAG, "POST connection refused for " + peer.host + ":" + peer.port, exception);
            throw new TransportFailure(TransportFailure.Kind.CONNECTION_REFUSED, exception.getMessage(), exception);
        } catch (UnknownHostException | NoRouteToHostException exception) {
            Log.w(TAG, "POST host unreachable for " + peer.host + ":" + peer.port, exception);
            throw new TransportFailure(TransportFailure.Kind.HOST_UNREACHABLE, exception.getMessage(), exception);
        } catch (TransportFailure exception) {
            throw exception;
        } catch (IOException exception) {
            Log.w(TAG, "POST IO failure for " + peer.host + ":" + peer.port, exception);
            throw new TransportFailure(TransportFailure.Kind.GENERIC_IO, exception.getMessage(), exception);
        } finally {
            if (connection != null) {
                connection.disconnect();
            }
        }
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

    private static TransportFailure mapHttpFailure(int status, String response) {
        if (status == 403 && response.contains("pair_code_rejected")) {
            return new TransportFailure(TransportFailure.Kind.PAIR_CODE_REJECTED, response, status, null);
        }
        if (status == 403 && response.contains("peer_not_paired")) {
            return new TransportFailure(TransportFailure.Kind.PEER_NOT_PAIRED, response, status, null);
        }
        if (status == 403 && response.contains("invalid_signature")) {
            return new TransportFailure(TransportFailure.Kind.SIGNATURE_REJECTED, response, status, null);
        }
        return new TransportFailure(TransportFailure.Kind.HTTP_FAILURE, response, status, null);
    }
}
