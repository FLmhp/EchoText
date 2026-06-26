package org.echotext.echotext.core;

import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.Iterator;
import java.util.List;
import java.util.Map;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

public final class JsonUtils {
    private JsonUtils() {}

    public static byte[] canonicalJsonBytes(Object value) throws JSONException {
        StringBuilder builder = new StringBuilder();
        appendJson(builder, value);
        return builder.toString().getBytes(StandardCharsets.UTF_8);
    }

    public static String canonicalJsonString(Object value) throws JSONException {
        return new String(canonicalJsonBytes(value), StandardCharsets.UTF_8);
    }

    private static void appendJson(StringBuilder builder, Object value) throws JSONException {
        if (value == null || value == JSONObject.NULL) {
            builder.append("null");
            return;
        }
        if (value instanceof JSONObject object) {
            List<String> keys = new ArrayList<>();
            Iterator<String> iterator = object.keys();
            while (iterator.hasNext()) {
                keys.add(iterator.next());
            }
            Collections.sort(keys);
            builder.append("{");
            boolean first = true;
            for (String key : keys) {
                if (!first) {
                    builder.append(",");
                }
                first = false;
                appendString(builder, key);
                builder.append(":");
                appendJson(builder, object.get(key));
            }
            builder.append("}");
            return;
        }
        if (value instanceof JSONArray array) {
            builder.append("[");
            for (int i = 0; i < array.length(); i++) {
                if (i > 0) {
                    builder.append(",");
                }
                appendJson(builder, array.get(i));
            }
            builder.append("]");
            return;
        }
        if (value instanceof Map<?, ?> map) {
            List<String> keys = new ArrayList<>();
            for (Object key : map.keySet()) {
                keys.add(String.valueOf(key));
            }
            Collections.sort(keys);
            builder.append("{");
            boolean first = true;
            for (String key : keys) {
                if (!first) {
                    builder.append(",");
                }
                first = false;
                appendString(builder, key);
                builder.append(":");
                appendJson(builder, map.get(key));
            }
            builder.append("}");
            return;
        }
        if (value instanceof Collection<?> collection) {
            builder.append("[");
            boolean first = true;
            for (Object item : collection) {
                if (!first) {
                    builder.append(",");
                }
                first = false;
                appendJson(builder, item);
            }
            builder.append("]");
            return;
        }
        if (value instanceof String stringValue) {
            appendString(builder, stringValue);
            return;
        }
        if (value instanceof Boolean) {
            builder.append(value);
            return;
        }
        if (value instanceof Float floatValue) {
            builder.append(BigDecimal.valueOf(floatValue.doubleValue()).toPlainString());
            return;
        }
        if (value instanceof Double doubleValue) {
            builder.append(BigDecimal.valueOf(doubleValue).toPlainString());
            return;
        }
        if (value instanceof Number) {
            builder.append(value);
            return;
        }
        appendString(builder, String.valueOf(value));
    }

    private static void appendString(StringBuilder builder, String value) {
        builder.append("\"");
        for (int i = 0; i < value.length(); i++) {
            char character = value.charAt(i);
            switch (character) {
                case '"':
                    builder.append("\\\"");
                    break;
                case '\\':
                    builder.append("\\\\");
                    break;
                case '\b':
                    builder.append("\\b");
                    break;
                case '\f':
                    builder.append("\\f");
                    break;
                case '\n':
                    builder.append("\\n");
                    break;
                case '\r':
                    builder.append("\\r");
                    break;
                case '\t':
                    builder.append("\\t");
                    break;
                default:
                    if (character < 0x20) {
                        builder.append(String.format("\\u%04x", (int) character));
                    } else {
                        builder.append(character);
                    }
                    break;
            }
        }
        builder.append("\"");
    }
}
