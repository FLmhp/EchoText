package org.echotext.echotext.model;

import org.json.JSONException;
import org.json.JSONObject;

public class HistoryEntry {
    public final String direction;
    public final String peerName;
    public final String text;
    public final double createdAt;
    public final String messageId;

    public HistoryEntry(String direction, String peerName, String text, double createdAt, String messageId) {
        this.direction = direction;
        this.peerName = peerName;
        this.text = text;
        this.createdAt = createdAt;
        this.messageId = messageId;
    }

    public JSONObject toJson() throws JSONException {
        JSONObject object = new JSONObject();
        object.put("direction", direction);
        object.put("peer_name", peerName);
        object.put("text", text);
        object.put("created_at", createdAt);
        object.put("message_id", messageId);
        return object;
    }

    public static HistoryEntry fromJson(JSONObject object) throws JSONException {
        return new HistoryEntry(
                object.getString("direction"),
                object.getString("peer_name"),
                object.getString("text"),
                object.getDouble("created_at"),
                object.getString("message_id"));
    }
}
