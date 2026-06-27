package org.echotext.echotext.core;

import android.content.Context;
import android.os.Handler;
import android.os.Looper;

import java.io.IOException;
import java.security.GeneralSecurityException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CopyOnWriteArrayList;

import org.echotext.echotext.model.DeviceIdentity;
import org.echotext.echotext.model.HistoryEntry;
import org.echotext.echotext.model.Peer;
import org.echotext.echotext.model.TextMessage;
import org.json.JSONException;

public class EchoTextController {
    public interface Listener {
        void onPeersChanged();

        void onHistoryChanged(HistoryEntry newestEntry);

        void onPeerPaired(Peer peer);
    }

    private final Context context;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private final CopyOnWriteArrayList<Listener> listeners = new CopyOnWriteArrayList<>();

    private SettingsStore settings;
    private PairCodeManager pairCodeManager;
    private HistoryStore historyStore;
    private TransportClient transportClient;
    private TransportServer transportServer;
    private DiscoveryService discoveryService;
    private DeviceIdentity identity;
    private Map<String, Peer> pairedPeers = new LinkedHashMap<>();
    private volatile boolean started;
    private volatile String latestText = "";

    public EchoTextController(Context context) {
        this.context = context.getApplicationContext();
    }

    public synchronized void start() throws IOException {
        if (started) {
            return;
        }
        settings = new SettingsStore(context);
        pairCodeManager = new PairCodeManager();
        historyStore = new HistoryStore(context, settings.isPersistentHistoryEnabled(), 100);
        transportClient = new TransportClient();
        List<String> hosts = LanNetwork.lanIpv4Candidates();
        String host = hosts.isEmpty() ? "127.0.0.1" : hosts.get(0);
        identity = settings.identity(host, 0, hosts);
        pairedPeers = new LinkedHashMap<>(settings.loadPeers());

        transportServer = new TransportServer(
                this::getIdentity,
                code -> pairCodeManager.matches(code),
                this::getPairedPeer,
                this::handleIncomingMessage,
                this::handlePeerPaired);
        transportServer.start();
        refreshIdentity(transportServer.getPort());

        discoveryService = new DiscoveryService(context, this::getIdentity, this::notifyPeersChanged);
        discoveryService.start();
        started = true;
    }

    public synchronized void stop() {
        if (!started) {
            return;
        }
        if (discoveryService != null) {
            discoveryService.stop();
        }
        if (transportServer != null) {
            transportServer.stop();
        }
        started = false;
    }

    public DeviceIdentity getIdentity() {
        refreshIdentity(transportServer == null ? 0 : transportServer.getPort());
        return identity;
    }

    public String getPairCode() {
        return pairCodeManager.getCode();
    }

    public List<Peer> getPeers() {
        Map<String, Peer> merged = new LinkedHashMap<>();
        if (discoveryService != null) {
            for (Peer discovered : discoveryService.peers()) {
                Peer paired = pairedPeers.get(discovered.deviceId);
                if (paired == null) {
                    merged.put(discovered.deviceId, discovered);
                } else {
                    List<String> hosts = LanNetwork.normalizeHosts(
                            discovered.host,
                            mergeHosts(discovered.hosts, paired.host, paired.hosts));
                    merged.put(
                            discovered.deviceId,
                            new Peer(
                                    paired.deviceId,
                                    paired.name,
                                    paired.platform,
                                    hosts.get(0),
                                    discovered.port,
                                    hosts,
                                    discovered.lastSeen,
                                    paired.sharedSecret));
                }
            }
        }
        for (Peer paired : pairedPeers.values()) {
            merged.putIfAbsent(paired.deviceId, paired);
        }
        List<Peer> peers = new ArrayList<>(merged.values());
        peers.sort(Comparator.comparing(peer -> peer.name.toLowerCase()));
        return dedupePeers(peers);
    }

    public synchronized Peer pairWithPeer(Peer peer, String pairCode) throws IOException, JSONException {
        String sharedSecret = SecurityUtils.generateSharedSecret();
        TransportClient.PairResult pairResult = transportClient.pair(peer, getIdentity(), pairCode, sharedSecret);
        DeviceIdentity peerIdentity = pairResult.identity;
        if (peer.deviceId != null && !peer.deviceId.isBlank() && !peer.deviceId.equals(peerIdentity.deviceId)) {
            throw new IOException("Reached another device at a stale address. Refresh the device list and try again.");
        }
        List<String> hosts = LanNetwork.normalizeHosts(
                pairResult.connectedHost,
                mergeHosts(peer.hosts, peerIdentity.host, peerIdentity.hosts));
        Peer paired =
                new Peer(
                        peerIdentity.deviceId,
                        peerIdentity.name,
                        peerIdentity.platform,
                        hosts.get(0),
                        peerIdentity.port,
                        hosts,
                        System.currentTimeMillis() / 1000.0,
                        sharedSecret);
        savePeer(paired);
        return paired;
    }

    public synchronized HistoryEntry sendText(Peer peer, String text)
            throws IOException, JSONException, GeneralSecurityException {
        Peer paired = pairedPeers.get(peer.deviceId);
        if (paired == null || paired.sharedSecret == null) {
            throw new IOException("Pair with the device before sending text");
        }
        Peer activePeer =
                new Peer(
                        paired.deviceId,
                        paired.name,
                        paired.platform,
                        peer.host,
                        peer.port,
                        LanNetwork.normalizeHosts(peer.host, mergeHosts(peer.hosts, paired.host, paired.hosts)),
                        peer.lastSeen,
                        paired.sharedSecret);
        TextMessage message = new TextMessage(
                UUID.randomUUID().toString().replace("-", ""),
                identity.deviceId,
                identity.name,
                text,
                System.currentTimeMillis() / 1000.0);
        String connectedHost = transportClient.sendMessage(activePeer, message);
        List<String> hosts = LanNetwork.normalizeHosts(
                connectedHost,
                mergeHosts(activePeer.hosts, paired.host, paired.hosts));
        savePeer(
                new Peer(
                        paired.deviceId,
                        paired.name,
                        paired.platform,
                        hosts.get(0),
                        activePeer.port,
                        hosts,
                        System.currentTimeMillis() / 1000.0,
                        paired.sharedSecret));
        HistoryEntry entry = new HistoryEntry("sent", activePeer.name, text, message.createdAt, message.messageId);
        latestText = text;
        historyStore.add(entry);
        notifyHistoryChanged(entry);
        return entry;
    }

    public synchronized void setPersistentHistory(boolean enabled) {
        settings.setPersistentHistoryEnabled(enabled);
        historyStore.setPersistent(enabled);
    }

    public boolean isPersistentHistoryEnabled() {
        return settings.isPersistentHistoryEnabled();
    }

    public synchronized void setAutoSyncEnabled(boolean enabled) {
        settings.setAutoSyncEnabled(enabled);
    }

    public boolean isAutoSyncEnabled() {
        return settings.isAutoSyncEnabled();
    }

    public synchronized void refreshDiscovery() {
        if (!started || discoveryService == null) {
            return;
        }
        refreshIdentity(transportServer == null ? 0 : transportServer.getPort());
        discoveryService.probe();
    }

    public synchronized Peer resolvePeer(String endpointText) throws IOException, JSONException {
        LanNetwork.HostEndpoint endpoint = LanNetwork.parseHostEndpoint(endpointText, LanNetwork.DEFAULT_ECHOTEXT_PORT);
        DeviceIdentity peerIdentity = transportClient.hello(endpoint.host, endpoint.port, 2_500);
        Peer existing = pairedPeers.get(peerIdentity.deviceId);
        List<String> hosts = LanNetwork.normalizeHosts(
                endpoint.host,
                mergeHosts(
                        peerIdentity.hosts,
                        peerIdentity.host,
                        existing == null ? java.util.Collections.emptyList() : existing.hosts));
        Peer resolved =
                new Peer(
                        peerIdentity.deviceId,
                        peerIdentity.name,
                        peerIdentity.platform,
                        hosts.get(0),
                        peerIdentity.port,
                        hosts,
                        System.currentTimeMillis() / 1000.0,
                        existing == null ? null : existing.sharedSecret);
        if (existing == null) {
            if (discoveryService != null) {
                discoveryService.rememberPeer(resolved);
                return resolved;
            }
        } else {
            pairedPeers.put(resolved.deviceId, resolved);
        }
        notifyPeersChanged();
        return resolved;
    }

    public String getLocalIpv6Address() {
        List<String> candidates = LanNetwork.lanIpv6Candidates();
        return candidates.isEmpty() ? null : candidates.get(0);
    }

    public synchronized void clearHistory() {
        latestText = "";
        historyStore.clear();
        notifyHistoryChanged(null);
    }

    public List<HistoryEntry> getHistory() {
        return historyStore.snapshot();
    }

    public String getLatestText() {
        return latestText;
    }

    public void addListener(Listener listener) {
        listeners.addIfAbsent(listener);
    }

    public void removeListener(Listener listener) {
        listeners.remove(listener);
    }

    private synchronized Peer getPairedPeer(String deviceId) {
        return pairedPeers.get(deviceId);
    }

    private synchronized void handleIncomingMessage(TextMessage message, Peer peer) {
        savePeer(peer);
        HistoryEntry entry = new HistoryEntry("received", peer.name, message.text, message.createdAt, message.messageId);
        latestText = message.text;
        historyStore.add(entry);
        notifyHistoryChanged(entry);
    }

    private synchronized void handlePeerPaired(Peer peer) {
        savePeer(peer);
        mainHandler.post(() -> {
            for (Listener listener : listeners) {
                listener.onPeerPaired(peer);
            }
            notifyPeersChanged();
        });
    }

    private synchronized void savePeer(Peer peer) {
        pairedPeers.put(peer.deviceId, peer);
        settings.savePeer(peer);
    }

    private synchronized void refreshIdentity(int port) {
        List<String> hosts = LanNetwork.lanIpv4Candidates();
        String host = hosts.isEmpty() ? "127.0.0.1" : hosts.get(0);
        if (identity != null
                && identity.port == port
                && identity.host.equals(host)
                && identity.hosts.equals(LanNetwork.normalizeHosts(host, hosts))) {
            return;
        }
        identity = settings.identity(host, port, hosts);
    }

    private static List<String> mergeHosts(List<String> hosts, String otherHost, List<String> otherHosts) {
        List<String> merged = new ArrayList<>(hosts);
        merged.add(otherHost);
        merged.addAll(otherHosts);
        return merged;
    }

    private static List<Peer> dedupePeers(List<Peer> peers) {
        Map<String, Peer> chosen = new LinkedHashMap<>();
        for (Peer peer : peers) {
            String key = peer.name.toLowerCase() + "\u0000" + peer.platform.toLowerCase();
            Peer existing = chosen.get(key);
            if (existing == null || peerRank(peer) > peerRank(existing)) {
                chosen.put(key, peer);
            }
        }
        List<Peer> deduped = new ArrayList<>(chosen.values());
        deduped.sort(Comparator.comparing(peer -> peer.name.toLowerCase()));
        return deduped;
    }

    private static double peerRank(Peer peer) {
        return peer.lastSeen + (peer.sharedSecret == null ? 0.0 : 0.001);
    }

    private void notifyPeersChanged() {
        mainHandler.post(() -> {
            for (Listener listener : listeners) {
                listener.onPeersChanged();
            }
        });
    }

    private void notifyHistoryChanged(HistoryEntry newestEntry) {
        mainHandler.post(() -> {
            for (Listener listener : listeners) {
                listener.onHistoryChanged(newestEntry);
            }
        });
    }
}
