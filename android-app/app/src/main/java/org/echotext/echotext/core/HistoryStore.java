package org.echotext.echotext.core;

import android.content.Context;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

import org.echotext.echotext.model.HistoryEntry;
import org.json.JSONArray;
import org.json.JSONException;

public class HistoryStore {
    private final File path;
    private final int limit;
    private boolean persistent;
    private final List<HistoryEntry> entries = new ArrayList<>();

    public HistoryStore(Context context, boolean persistent, int limit) {
        this.path = new File(context.getFilesDir(), "history.json");
        this.persistent = persistent;
        this.limit = limit;
        if (persistent) {
            load();
        }
    }

    public synchronized List<HistoryEntry> snapshot() {
        return new ArrayList<>(entries);
    }

    public synchronized void setPersistent(boolean persistent) {
        this.persistent = persistent;
        if (persistent) {
            save();
        } else if (path.exists()) {
            //noinspection ResultOfMethodCallIgnored
            path.delete();
        }
    }

    public synchronized void add(HistoryEntry entry) {
        for (HistoryEntry existing : entries) {
            if (existing.messageId.equals(entry.messageId)) {
                return;
            }
        }
        entries.add(entry);
        while (entries.size() > limit) {
            entries.remove(0);
        }
        if (persistent) {
            save();
        }
    }

    public synchronized void clear() {
        entries.clear();
        if (path.exists()) {
            //noinspection ResultOfMethodCallIgnored
            path.delete();
        }
    }

    private void load() {
        if (!path.exists()) {
            return;
        }
        try (FileInputStream inputStream = new FileInputStream(path);
             InputStreamReader reader = new InputStreamReader(inputStream, StandardCharsets.UTF_8)) {
            StringBuilder rawBuilder = new StringBuilder();
            char[] buffer = new char[4096];
            int read;
            while ((read = reader.read(buffer)) != -1) {
                rawBuilder.append(buffer, 0, read);
            }
            String raw = rawBuilder.toString();
            JSONArray array = new JSONArray(raw);
            entries.clear();
            for (int i = Math.max(0, array.length() - limit); i < array.length(); i++) {
                entries.add(HistoryEntry.fromJson(array.getJSONObject(i)));
            }
        } catch (IOException | JSONException ignored) {
            entries.clear();
        }
    }

    private void save() {
        JSONArray array = new JSONArray();
        synchronized (this) {
            for (HistoryEntry entry : entries) {
                try {
                    array.put(entry.toJson());
                } catch (JSONException ignored) {
                    // Skip malformed entry.
                }
            }
        }
        try (FileOutputStream outputStream = new FileOutputStream(path);
             OutputStreamWriter writer = new OutputStreamWriter(outputStream, StandardCharsets.UTF_8)) {
            writer.write(array.toString());
        } catch (IOException ignored) {
            // Best-effort persistence.
        }
    }
}
