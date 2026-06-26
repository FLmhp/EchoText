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
        String host = LanNetwork.localLanIp();
        identity = settings.identity(host, 0);
        pairedPeers = new LinkedHashMap<>(settings.loadPeers());

        transportServer = new TransportServer(
                this::getIdentity,
                code -> pairCodeManager.matches(code),
                this::getPairedPeer,
                this::handleIncomingMessage,
                this::handlePeerPaired);
        transportServer.start();
        identity = settings.identity(host, transportServer.getPort());

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
                    merged.put(
                            discovered.deviceId,
                            new Peer(
                                    paired.deviceId,
                                    paired.name,
                                    paired.platform,
                                    discovered.host,
                                    discovered.port,
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
        return peers;
    }

    public synchronized Peer pairWithPeer(Peer peer, String pairCode) throws IOException, JSONException {
        String sharedSecret = SecurityUtils.generateSharedSecret();
        DeviceIdentity peerIdentity = transportClient.pair(peer, identity, pairCode, sharedSecret);
        Peer paired =
                new Peer(peerIdentity.deviceId, peerIdentity.name, peerIdentity.platform, peerIdentity.host, peerIdentity.port,
                        System.currentTimeMillis() / 1000.0, sharedSecret);
        savePeer(paired);
        return paired;
    }

    public synchronized HistoryEntry sendText(Peer peer, String text)
            throws IOException, JSONException, GeneralSecurityException {
        Peer paired = pairedPeers.get(peer.deviceId);
        if (paired == null || paired.sharedSecret == null) {
            throw new IOException("Pair with the device before sending text");
        }
        TextMessage message = new TextMessage(
                UUID.randomUUID().toString().replace("-", ""),
                identity.deviceId,
                identity.name,
                text,
                System.currentTimeMillis() / 1000.0);
        transportClient.sendMessage(paired, message);
        HistoryEntry entry = new HistoryEntry("sent", paired.name, text, message.createdAt, message.messageId);
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

    public synchronized void setLanguagePreference(String language) {
        settings.setLanguagePreference(language);
    }

    public String getLanguagePreference() {
        return settings.getLanguagePreference();
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
