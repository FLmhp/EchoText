package org.echotext.echotext.core;

import android.content.Context;
import android.net.wifi.WifiManager;

import java.io.IOException;
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.SocketException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

import org.echotext.echotext.model.DeviceIdentity;
import org.echotext.echotext.model.Peer;
import org.json.JSONObject;

public class DiscoveryService {
    public interface IdentityProvider {
        DeviceIdentity identity() throws Exception;
    }

    private static final int DISCOVERY_PORT = 48734;
    private static final String DISCOVERY_MAGIC = "ECHOTEXT_DISCOVERY_V1";

    private final Context context;
    private final IdentityProvider identityProvider;
    private final Runnable onPeersChanged;
    private final Map<String, Peer> peers = new ConcurrentHashMap<>();
    private final AtomicBoolean running = new AtomicBoolean(false);
    private final ExecutorService executor = Executors.newFixedThreadPool(2);

    private DatagramSocket broadcastSocket;
    private DatagramSocket listenSocket;
    private WifiManager.MulticastLock multicastLock;

    public DiscoveryService(Context context, IdentityProvider identityProvider, Runnable onPeersChanged) {
        this.context = context.getApplicationContext();
        this.identityProvider = identityProvider;
        this.onPeersChanged = onPeersChanged;
    }

    public void start() {
        if (!running.compareAndSet(false, true)) {
            return;
        }
        acquireMulticastLock();
        executor.execute(this::broadcastLoop);
        executor.execute(this::listenLoop);
    }

    public void stop() {
        running.set(false);
        if (broadcastSocket != null) {
            broadcastSocket.close();
        }
        if (listenSocket != null) {
            listenSocket.close();
        }
        executor.shutdownNow();
        releaseMulticastLock();
    }

    public List<Peer> peers() {
        List<Peer> snapshot = new ArrayList<>(peers.values());
        snapshot.sort(Comparator.comparing(peer -> peer.name.toLowerCase()));
        return snapshot;
    }

    private void broadcastLoop() {
        try {
            broadcastSocket = new DatagramSocket();
            broadcastSocket.setBroadcast(true);
            while (running.get()) {
                DeviceIdentity identity = identityProvider.identity();
                JSONObject payload = new JSONObject();
                payload.put("magic", DISCOVERY_MAGIC);
                payload.put("device", identity.toJson());
                byte[] bytes = payload.toString().getBytes(StandardCharsets.UTF_8);
                DatagramPacket packet =
                        new DatagramPacket(bytes, bytes.length, InetAddress.getByName("255.255.255.255"), DISCOVERY_PORT);
                broadcastSocket.send(packet);
                Thread.sleep(2_000L);
            }
        } catch (Exception ignored) {
            // Background best-effort broadcast.
        } finally {
            if (broadcastSocket != null) {
                broadcastSocket.close();
            }
        }
    }

    private void listenLoop() {
        try {
            listenSocket = new DatagramSocket(null);
            listenSocket.setReuseAddress(true);
            listenSocket.bind(new InetSocketAddress(DISCOVERY_PORT));
            listenSocket.setSoTimeout(1_000);
            byte[] buffer = new byte[8192];
            while (running.get()) {
                DatagramPacket packet = new DatagramPacket(buffer, buffer.length);
                try {
                    listenSocket.receive(packet);
                    handlePacket(packet);
                } catch (java.net.SocketTimeoutException ignored) {
                    // Loop again.
                } catch (SocketException ignored) {
                    // Socket closed during shutdown.
                }
            }
        } catch (IOException ignored) {
            // Best-effort listener.
        } finally {
            if (listenSocket != null) {
                listenSocket.close();
            }
        }
    }

    private void handlePacket(DatagramPacket packet) {
        try {
            String raw = new String(packet.getData(), packet.getOffset(), packet.getLength(), StandardCharsets.UTF_8);
            JSONObject payload = new JSONObject(raw);
            if (!DISCOVERY_MAGIC.equals(payload.optString("magic"))) {
                return;
            }
            DeviceIdentity identity = DeviceIdentity.fromJson(payload.getJSONObject("device"));
            DeviceIdentity local = identityProvider.identity();
            if (identity.deviceId.equals(local.deviceId)) {
                return;
            }
            String sourceHost = packet.getAddress().getHostAddress();
            String host = "127.0.0.1".equals(identity.host) ? sourceHost : identity.host;
            Peer peer =
                    new Peer(identity.deviceId, identity.name, identity.platform, host, identity.port,
                            System.currentTimeMillis() / 1000.0, null);
            peers.put(peer.deviceId, peer);
            onPeersChanged.run();
        } catch (Exception ignored) {
            // Ignore malformed packets.
        }
    }

    private void acquireMulticastLock() {
        Object service = context.getSystemService(Context.WIFI_SERVICE);
        if (!(service instanceof WifiManager manager)) {
            return;
        }
        multicastLock = manager.createMulticastLock("echotext-discovery");
        multicastLock.setReferenceCounted(false);
        multicastLock.acquire();
    }

    private void releaseMulticastLock() {
        if (multicastLock != null && multicastLock.isHeld()) {
            multicastLock.release();
        }
    }
}
