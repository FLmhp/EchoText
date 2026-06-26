package org.echotext.echotext.core;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.Build;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

import org.echotext.echotext.model.DeviceIdentity;
import org.echotext.echotext.model.Peer;
import org.json.JSONException;
import org.json.JSONObject;

public class SettingsStore {
    public static final String PREFS_NAME = "echotext_settings";

    private static final String KEY_DEVICE_ID = "device_id";
    private static final String KEY_DEVICE_NAME = "device_name";
    private static final String KEY_LANGUAGE = "language";
    private static final String KEY_PERSISTENT_HISTORY = "persistent_history";
    private static final String KEY_AUTO_SYNC = "auto_sync";
    private static final String KEY_PEERS = "peers";

    private final SharedPreferences preferences;

    public SettingsStore(Context context) {
        this.preferences = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
    }

    public DeviceIdentity identity(String host, int port) {
        if (!preferences.contains(KEY_DEVICE_ID)) {
            preferences.edit().putString(KEY_DEVICE_ID, UUID.randomUUID().toString().replace("-", "")).apply();
        }
        if (!preferences.contains(KEY_DEVICE_NAME)) {
            preferences.edit().putString(KEY_DEVICE_NAME, defaultDeviceName()).apply();
        }
        return new DeviceIdentity(
                preferences.getString(KEY_DEVICE_ID, ""),
                preferences.getString(KEY_DEVICE_NAME, defaultDeviceName()),
                "Android",
                host,
                port);
    }

    public Map<String, Peer> loadPeers() {
        Map<String, Peer> peers = new LinkedHashMap<>();
        String raw = preferences.getString(KEY_PEERS, "{}");
        try {
            JSONObject object = new JSONObject(raw);
            java.util.Iterator<String> keys = object.keys();
            while (keys.hasNext()) {
                String key = keys.next();
                peers.put(key, Peer.fromJson(object.getJSONObject(key)));
            }
        } catch (JSONException ignored) {
            // Ignore corrupted data and start fresh.
        }
        return peers;
    }

    public void savePeer(Peer peer) {
        try {
            JSONObject peers = new JSONObject(preferences.getString(KEY_PEERS, "{}"));
            peers.put(peer.deviceId, peer.toJson());
            preferences.edit().putString(KEY_PEERS, peers.toString()).apply();
        } catch (JSONException ignored) {
            // Ignore save failures for malformed legacy data.
        }
    }

    public boolean isPersistentHistoryEnabled() {
        return preferences.getBoolean(KEY_PERSISTENT_HISTORY, false);
    }

    public void setPersistentHistoryEnabled(boolean enabled) {
        preferences.edit().putBoolean(KEY_PERSISTENT_HISTORY, enabled).apply();
    }

    public boolean isAutoSyncEnabled() {
        return preferences.getBoolean(KEY_AUTO_SYNC, false);
    }

    public void setAutoSyncEnabled(boolean enabled) {
        preferences.edit().putBoolean(KEY_AUTO_SYNC, enabled).apply();
    }

    public String getLanguagePreference() {
        return preferences.getString(KEY_LANGUAGE, "auto");
    }

    public void setLanguagePreference(String language) {
        preferences.edit().putString(KEY_LANGUAGE, language).apply();
    }

    public static String peekLanguagePreference(Context context) {
        return context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE).getString(KEY_LANGUAGE, "auto");
    }

    private static String defaultDeviceName() {
        String manufacturer = Build.MANUFACTURER == null ? "" : Build.MANUFACTURER.trim();
        String model = Build.MODEL == null ? "" : Build.MODEL.trim();
        String name = (manufacturer + " " + model).trim();
        return name.isEmpty() ? "EchoText Android" : name;
    }
}
