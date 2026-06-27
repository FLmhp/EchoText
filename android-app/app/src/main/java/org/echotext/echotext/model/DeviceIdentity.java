package org.echotext.echotext.model;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

import org.echotext.echotext.core.LanNetwork;
import org.json.JSONException;
import org.json.JSONArray;
import org.json.JSONObject;

public class DeviceIdentity {
    public final String deviceId;
    public final String name;
    public final String platform;
    public final String host;
    public final int port;
    public final List<String> hosts;

    public DeviceIdentity(String deviceId, String name, String platform, String host, int port) {
        this(deviceId, name, platform, host, port, Collections.singletonList(host));
    }

    public DeviceIdentity(String deviceId, String name, String platform, String host, int port, List<String> hosts) {
        this.deviceId = deviceId;
        this.name = name;
        this.platform = platform;
        this.host = host;
        this.port = port;
        this.hosts = Collections.unmodifiableList(new ArrayList<>(LanNetwork.normalizeHosts(host, hosts)));
    }

    public JSONObject toJson() throws JSONException {
        JSONObject object = new JSONObject();
        object.put("device_id", deviceId);
        object.put("name", name);
        object.put("platform", platform);
        object.put("host", host);
        object.put("port", port);
        JSONArray hostArray = new JSONArray();
        for (String value : hosts) {
            hostArray.put(value);
        }
        object.put("hosts", hostArray);
        return object;
    }

    public static DeviceIdentity fromJson(JSONObject object) throws JSONException {
        List<String> hosts = new ArrayList<>();
        JSONArray hostArray = object.optJSONArray("hosts");
        if (hostArray != null) {
            for (int index = 0; index < hostArray.length(); index++) {
                hosts.add(hostArray.optString(index));
            }
        }
        return new DeviceIdentity(
                object.getString("device_id"),
                object.getString("name"),
                object.getString("platform"),
                object.getString("host"),
                object.getInt("port"),
                hosts);
    }
}
