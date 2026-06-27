package org.echotext.echotext.core;

import android.content.Context;
import android.net.wifi.WifiManager;
import android.util.Log;

import org.echotext.echotext.model.DeviceIdentity;
import org.echotext.echotext.model.Peer;
import org.json.JSONObject;

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
import java.util.Objects;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorCompletionService;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

public class DiscoveryService {
    public interface IdentityProvider {
        DeviceIdentity identity() throws Exception;
    }

    private static final int DISCOVERY_PORT = 48734;
    private static final String DISCOVERY_MAGIC = "ECHOTEXT_DISCOVERY_V1";
    private static final String DISCOVERY_REQUEST_MAGIC = "ECHOTEXT_DISCOVERY_REQ_V1";
    private static final String TAG = "EchoTextDiscovery";

    private final Context context;
    private final IdentityProvider identityProvider;
    private final Runnable onPeersChanged;
    private final Map<String, Peer> peers = new ConcurrentHashMap<>();
    private final AtomicBoolean running = new AtomicBoolean(false);
    private final AtomicBoolean probeRunning = new AtomicBoolean(false);
    private final ExecutorService executor = Executors.newCachedThreadPool();
    private final TransportClient transportClient = new TransportClient();

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
        probe();
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

    public void probe() {
        if (!running.get() || !probeRunning.compareAndSet(false, true)) {
            return;
        }
        executor.execute(() -> {
            try {
                probeLoop();
            } finally {
                probeRunning.set(false);
            }
        });
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
                for (String target : LanNetwork.broadcastTargets(identity.hosts)) {
                    DatagramPacket packet =
                            new DatagramPacket(bytes, bytes.length, InetAddress.getByName(target), DISCOVERY_PORT);
                    broadcastSocket.send(packet);
                }
                Thread.sleep(2_000L);
            }
        } catch (Exception exception) {
            Log.w(TAG, "Discovery broadcast stopped", exception);
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
            listenSocket.setBroadcast(true);
            listenSocket.bind(new InetSocketAddress(DISCOVERY_PORT));
            listenSocket.setSoTimeout(1_000);
            byte[] buffer = new byte[8192];
            while (running.get()) {
                DatagramPacket packet = new DatagramPacket(buffer, buffer.length);
                try {
                    listenSocket.receive(packet);
                    handlePacket(listenSocket, packet);
                } catch (java.net.SocketTimeoutException ignored) {
                    // Loop again.
                } catch (SocketException ignored) {
                    // Socket closed during shutdown.
                }
            }
        } catch (IOException exception) {
            Log.w(TAG, "Discovery listener stopped", exception);
        } finally {
            if (listenSocket != null) {
                listenSocket.close();
            }
        }
    }

    private void handlePacket(DatagramSocket socket, DatagramPacket packet) {
        try {
            String raw = new String(packet.getData(), packet.getOffset(), packet.getLength(), StandardCharsets.UTF_8);
            JSONObject payload = new JSONObject(raw);
            String magic = payload.optString("magic", "");
            if (DISCOVERY_REQUEST_MAGIC.equals(magic)) {
                replyToProbe(socket, packet.getAddress(), packet.getPort());
                return;
            }
            if (!DISCOVERY_MAGIC.equals(magic)) {
                return;
            }
            DeviceIdentity identity = DeviceIdentity.fromJson(payload.getJSONObject("device"));
            DeviceIdentity local = identityProvider.identity();
            if (identity.deviceId.equals(local.deviceId)) {
                return;
            }
            String sourceHost = packet.getAddress().getHostAddress();
            String host = LanNetwork.shouldPreferSourceHost(identity.host, sourceHost) ? sourceHost : identity.host;
            List<String> hosts = LanNetwork.normalizeHosts(host, mergeHosts(sourceHost, identity.hosts, identity.host));
            Peer peer =
                    new Peer(
                            identity.deviceId,
                            identity.name,
                            identity.platform,
                            hosts.get(0),
                            identity.port,
                            hosts,
                            System.currentTimeMillis() / 1000.0,
                            null);
            updatePeer(peer);
        } catch (Exception ignored) {
            // Ignore malformed packets.
        }
    }

    private void replyToProbe(DatagramSocket socket, InetAddress address, int port) {
        try {
            DeviceIdentity identity = identityProvider.identity();
            JSONObject payload = new JSONObject();
            payload.put("magic", DISCOVERY_MAGIC);
            payload.put("device", identity.toJson());
            byte[] bytes = payload.toString().getBytes(StandardCharsets.UTF_8);
            socket.send(new DatagramPacket(bytes, bytes.length, address, port));
        } catch (Exception exception) {
            Log.d(TAG, "Probe reply skipped", exception);
        }
    }

    private void probeLoop() {
        sendDiscoveryRequests();
        try {
            Thread.sleep(900L);
        } catch (InterruptedException ignored) {
            Thread.currentThread().interrupt();
            return;
        }
        scanHttpPeers();
    }

    private void sendDiscoveryRequests() {
        try (DatagramSocket socket = new DatagramSocket()) {
            socket.setBroadcast(true);
            DeviceIdentity identity = identityProvider.identity();
            JSONObject payload = new JSONObject();
            payload.put("magic", DISCOVERY_REQUEST_MAGIC);
            payload.put("device_id", identity.deviceId);
            byte[] bytes = payload.toString().getBytes(StandardCharsets.UTF_8);
            for (int round = 0; round < 3 && running.get(); round++) {
                for (String target : LanNetwork.broadcastTargets(identity.hosts)) {
                    try {
                        socket.send(new DatagramPacket(bytes, bytes.length, InetAddress.getByName(target), DISCOVERY_PORT));
                    } catch (IOException ignored) {
                        // Best effort.
                    }
                }
                Thread.sleep(200L);
            }
        } catch (Exception exception) {
            Log.d(TAG, "Discovery probe send failed", exception);
        }
    }

    private void scanHttpPeers() {
        try {
            if (!peers.isEmpty()) {
                return;
            }
            DeviceIdentity identity = identityProvider.identity();
            List<String> candidates = LanNetwork.subnetScanTargets(identity.hosts);
            if (candidates.isEmpty()) {
                return;
            }

            ExecutorService probeExecutor = Executors.newFixedThreadPool(48);
            ExecutorCompletionService<Peer> completion = new ExecutorCompletionService<>(probeExecutor);
            int submitted = 0;
            for (String host : candidates) {
                completion.submit(() -> probeCandidate(host));
                submitted += 1;
            }

            long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(8);
            try {
                for (int index = 0; index < submitted && running.get(); index++) {
                    long remainingNanos = deadline - System.nanoTime();
                    if (remainingNanos <= 0) {
                        return;
                    }
                    Future<Peer> future = completion.poll(remainingNanos, TimeUnit.NANOSECONDS);
                    if (future == null) {
                        return;
                    }
                    Peer peer = future.get();
                    if (peer != null) {
                        updatePeer(peer);
                        return;
                    }
                }
            } finally {
                probeExecutor.shutdownNow();
            }
        } catch (Exception exception) {
            Log.d(TAG, "HTTP peer scan skipped", exception);
        }
    }

    private Peer probeCandidate(String host) {
        try {
            DeviceIdentity identity = transportClient.hello(host, TransportServer.DEFAULT_PORT, 180);
            DeviceIdentity local = identityProvider.identity();
            if (identity.deviceId.equals(local.deviceId)) {
                return null;
            }
            List<String> hosts = LanNetwork.normalizeHosts(host, mergeHosts(host, identity.hosts, identity.host));
            return new Peer(
                    identity.deviceId,
                    identity.name,
                    identity.platform,
                    hosts.get(0),
                    identity.port,
                    hosts,
                    System.currentTimeMillis() / 1000.0,
                    null);
        } catch (Exception exception) {
            return null;
        }
    }

    private void updatePeer(Peer peer) {
        Peer existing = peers.put(peer.deviceId, peer);
        if (!samePeer(existing, peer)) {
            onPeersChanged.run();
        }
    }

    private static boolean samePeer(Peer left, Peer right) {
        if (left == null || right == null) {
            return left == right;
        }
        return Objects.equals(left.deviceId, right.deviceId)
                && Objects.equals(left.name, right.name)
                && Objects.equals(left.platform, right.platform)
                && Objects.equals(left.host, right.host)
                && left.port == right.port
                && Objects.equals(left.hosts, right.hosts)
                && Objects.equals(left.sharedSecret, right.sharedSecret);
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

    private static List<String> mergeHosts(String sourceHost, List<String> identityHosts, String advertisedHost) {
        List<String> merged = new ArrayList<>();
        merged.add(sourceHost);
        merged.add(advertisedHost);
        merged.addAll(identityHosts);
        return merged;
    }
}
