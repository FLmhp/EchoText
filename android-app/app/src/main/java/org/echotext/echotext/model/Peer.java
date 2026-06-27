package org.echotext.echotext.model;

import java.util.List;

import org.echotext.echotext.core.LanNetwork;
import org.json.JSONException;
import org.json.JSONObject;

public class Peer extends DeviceIdentity {
    public final double lastSeen;
    public final String sharedSecret;

    public Peer(
            String deviceId,
            String name,
            String platform,
            String host,
            int port,
            double lastSeen,
            String sharedSecret) {
        this(deviceId, name, platform, host, port, java.util.Collections.singletonList(host), lastSeen, sharedSecret);
    }

    public Peer(
            String deviceId,
            String name,
            String platform,
            String host,
            int port,
            List<String> hosts,
            double lastSeen,
            String sharedSecret) {
        super(deviceId, name, platform, host, port, hosts);
        this.lastSeen = lastSeen;
        this.sharedSecret = sharedSecret;
    }

    public Peer withConnection(String host, int port, double lastSeen) {
        return new Peer(deviceId, name, platform, host, port, hosts, lastSeen, sharedSecret);
    }

    public JSONObject toJson() throws JSONException {
        JSONObject object = super.toJson();
        object.put("last_seen", lastSeen);
        if (sharedSecret == null) {
            object.put("shared_secret", JSONObject.NULL);
        } else {
            object.put("shared_secret", sharedSecret);
        }
        return object;
    }

    public static Peer fromJson(JSONObject object) throws JSONException {
        DeviceIdentity identity = DeviceIdentity.fromJson(object);
        return new Peer(
                identity.deviceId,
                identity.name,
                identity.platform,
                identity.host,
                identity.port,
                LanNetwork.normalizeHosts(identity.host, identity.hosts),
                object.optDouble("last_seen", 0.0),
                object.isNull("shared_secret") ? null : object.optString("shared_secret", null));
    }
}
