package org.echotext.echotext.model;

import org.json.JSONException;
import org.json.JSONObject;

public class DeviceIdentity {
    public final String deviceId;
    public final String name;
    public final String platform;
    public final String host;
    public final int port;

    public DeviceIdentity(String deviceId, String name, String platform, String host, int port) {
        this.deviceId = deviceId;
        this.name = name;
        this.platform = platform;
        this.host = host;
        this.port = port;
    }

    public JSONObject toJson() throws JSONException {
        JSONObject object = new JSONObject();
        object.put("device_id", deviceId);
        object.put("name", name);
        object.put("platform", platform);
        object.put("host", host);
        object.put("port", port);
        return object;
    }

    public static DeviceIdentity fromJson(JSONObject object) throws JSONException {
        return new DeviceIdentity(
                object.getString("device_id"),
                object.getString("name"),
                object.getString("platform"),
                object.getString("host"),
                object.getInt("port"));
    }
}
