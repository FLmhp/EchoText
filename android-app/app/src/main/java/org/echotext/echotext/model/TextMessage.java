package org.echotext.echotext.model;

import org.json.JSONException;
import org.json.JSONObject;

public class TextMessage {
    public final String messageId;
    public final String senderId;
    public final String senderName;
    public final String text;
    public final double createdAt;

    public TextMessage(String messageId, String senderId, String senderName, String text, double createdAt) {
        this.messageId = messageId;
        this.senderId = senderId;
        this.senderName = senderName;
        this.text = text;
        this.createdAt = createdAt;
    }

    public JSONObject toJson() throws JSONException {
        JSONObject object = new JSONObject();
        object.put("message_id", messageId);
        object.put("sender_id", senderId);
        object.put("sender_name", senderName);
        object.put("text", text);
        object.put("created_at", createdAt);
        return object;
    }

    public static TextMessage fromJson(JSONObject object) throws JSONException {
        return new TextMessage(
                object.getString("message_id"),
                object.getString("sender_id"),
                object.getString("sender_name"),
                object.getString("text"),
                object.getDouble("created_at"));
    }
}
