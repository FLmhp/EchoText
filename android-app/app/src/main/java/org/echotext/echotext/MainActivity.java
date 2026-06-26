package org.echotext.echotext;

import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.Spinner;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.appcompat.widget.SwitchCompat;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

import org.echotext.echotext.core.EchoTextController;
import org.echotext.echotext.core.SettingsStore;
import org.echotext.echotext.model.HistoryEntry;
import org.echotext.echotext.model.Peer;
import org.echotext.echotext.ui.LocaleHelper;

public class MainActivity extends AppCompatActivity implements EchoTextController.Listener {
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Runnable refreshRunnable =
            new Runnable() {
                @Override
                public void run() {
                    refreshUi();
                    handler.postDelayed(this, 1_000L);
                }
            };

    private EchoTextController controller;
    private ClipboardManager clipboardManager;
    private ClipboardManager.OnPrimaryClipChangedListener clipboardListener;

    private TextView statusText;
    private TextView pairCodeText;
    private Spinner deviceSpinner;
    private Spinner languageSpinner;
    private EditText pairCodeInput;
    private EditText messageInput;
    private SwitchCompat autoSyncSwitch;
    private SwitchCompat persistentHistorySwitch;
    private TextView historyText;

    private ArrayAdapter<String> deviceAdapter;
    private ArrayAdapter<String> languageAdapter;
    private final List<Peer> displayedPeers = new ArrayList<>();
    private boolean suppressLanguageSelection;
    private String lastClipboardText = "";

    @Override
    protected void attachBaseContext(Context newBase) {
        super.attachBaseContext(LocaleHelper.wrap(newBase, SettingsStore.peekLanguagePreference(newBase)));
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        controller = ((EchoTextApplication) getApplication()).getController();
        try {
            controller.start();
        } catch (Exception exception) {
            throw new IllegalStateException("Failed to start EchoText", exception);
        }

        clipboardManager = (ClipboardManager) getSystemService(CLIPBOARD_SERVICE);
        clipboardListener =
                () -> {
                    if (!controller.isAutoSyncEnabled()) {
                        return;
                    }
                    String current = readClipboardText();
                    if (current.trim().isEmpty() || current.equals(lastClipboardText)) {
                        return;
                    }
                    lastClipboardText = current;
                    messageInput.setText(current);
                    sendSelectedText();
                };
        bindViews();
        configureLanguageSpinner();
        configureActions();
        refreshToggles();
        setStatus(getString(R.string.status_ready));
        refreshUi();
    }

    @Override
    protected void onResume() {
        super.onResume();
        controller.addListener(this);
        if (clipboardManager != null) {
            clipboardManager.addPrimaryClipChangedListener(clipboardListener);
        }
        handler.post(refreshRunnable);
    }

    @Override
    protected void onPause() {
        super.onPause();
        controller.removeListener(this);
        if (clipboardManager != null) {
            clipboardManager.removePrimaryClipChangedListener(clipboardListener);
        }
        handler.removeCallbacks(refreshRunnable);
    }

    @Override
    public void onPeersChanged() {
        refreshPeerList();
    }

    @Override
    public void onHistoryChanged(HistoryEntry newestEntry) {
        if (newestEntry != null && "received".equals(newestEntry.direction)) {
            copyToClipboard(newestEntry.text);
            setStatus(getString(R.string.status_received, newestEntry.peerName));
        }
        refreshHistory();
    }

    @Override
    public void onPeerPaired(Peer peer) {
        setStatus(getString(R.string.status_paired, peer.name));
        refreshPeerList();
    }

    private void bindViews() {
        statusText = findViewById(R.id.status_text);
        pairCodeText = findViewById(R.id.pair_code_text);
        deviceSpinner = findViewById(R.id.device_spinner);
        languageSpinner = findViewById(R.id.language_spinner);
        pairCodeInput = findViewById(R.id.pair_code_input);
        messageInput = findViewById(R.id.message_input);
        autoSyncSwitch = findViewById(R.id.auto_sync_switch);
        persistentHistorySwitch = findViewById(R.id.persistent_history_switch);
        historyText = findViewById(R.id.history_text);

        deviceAdapter = new ArrayAdapter<>(this, android.R.layout.simple_spinner_item, new ArrayList<>());
        deviceAdapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        deviceSpinner.setAdapter(deviceAdapter);
    }

    private void configureLanguageSpinner() {
        languageAdapter = new ArrayAdapter<>(
                this,
                android.R.layout.simple_spinner_item,
                Arrays.asList(
                        getString(R.string.language_auto),
                        getString(R.string.language_english),
                        getString(R.string.language_chinese)));
        languageAdapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        languageSpinner.setAdapter(languageAdapter);

        suppressLanguageSelection = true;
        languageSpinner.setSelection(languageIndex(controller.getLanguagePreference()));
        suppressLanguageSelection = false;

        languageSpinner.setOnItemSelectedListener(new android.widget.AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(android.widget.AdapterView<?> parent, android.view.View view, int position, long id) {
                if (suppressLanguageSelection) {
                    return;
                }
                String selected = switch (position) {
                    case 1 -> "en";
                    case 2 -> "zh";
                    default -> "auto";
                };
                if (!selected.equals(controller.getLanguagePreference())) {
                    controller.setLanguagePreference(selected);
                    recreate();
                }
            }

            @Override
            public void onNothingSelected(android.widget.AdapterView<?> parent) {}
        });
    }

    private void configureActions() {
        Button refreshButton = findViewById(R.id.refresh_button);
        Button pairButton = findViewById(R.id.pair_button);
        Button pasteButton = findViewById(R.id.paste_button);
        Button sendButton = findViewById(R.id.send_button);
        Button copyLatestButton = findViewById(R.id.copy_latest_button);
        Button clearButton = findViewById(R.id.clear_button);

        refreshButton.setOnClickListener(view -> refreshUi());
        pairButton.setOnClickListener(view -> pairSelectedPeer());
        pasteButton.setOnClickListener(view -> {
            String clipboardText = readClipboardText();
            if (clipboardManager == null) {
                setStatus(getString(R.string.status_clipboard_unavailable));
                return;
            }
            if (clipboardText.trim().isEmpty()) {
                setStatus(getString(R.string.status_clipboard_empty));
                return;
            }
            messageInput.setText(clipboardText);
        });
        sendButton.setOnClickListener(view -> sendSelectedText());
        copyLatestButton.setOnClickListener(view -> {
            String latest = controller.getLatestText();
            if (!latest.trim().isEmpty()) {
                copyToClipboard(latest);
            } else {
                setStatus(getString(R.string.status_nothing_to_copy));
            }
        });
        clearButton.setOnClickListener(view -> {
            controller.clearHistory();
            refreshHistory();
            setStatus(getString(R.string.status_history_cleared));
        });
        autoSyncSwitch.setOnCheckedChangeListener((buttonView, isChecked) -> controller.setAutoSyncEnabled(isChecked));
        persistentHistorySwitch.setOnCheckedChangeListener(
                (buttonView, isChecked) -> controller.setPersistentHistory(isChecked));
    }

    private void refreshUi() {
        refreshPeerList();
        refreshPairCode();
        refreshHistory();
        refreshToggles();
    }

    private void refreshToggles() {
        autoSyncSwitch.setChecked(controller.isAutoSyncEnabled());
        persistentHistorySwitch.setChecked(controller.isPersistentHistoryEnabled());
    }

    private void refreshPairCode() {
        org.echotext.echotext.model.DeviceIdentity identity = controller.getIdentity();
        if (identity == null) {
            return;
        }
        pairCodeText.setText(getString(R.string.pair_code_display, identity.name, identity.host, identity.port, controller.getPairCode()));
    }

    private void refreshPeerList() {
        List<Peer> peers = controller.getPeers();
        displayedPeers.clear();
        deviceAdapter.clear();
        if (peers.isEmpty()) {
            deviceAdapter.add(getString(R.string.no_devices));
            deviceSpinner.setEnabled(false);
            deviceAdapter.notifyDataSetChanged();
            return;
        }
        displayedPeers.addAll(peers);
        for (Peer peer : peers) {
            deviceAdapter.add(formatPeerLabel(peer));
        }
        deviceSpinner.setEnabled(true);
        deviceAdapter.notifyDataSetChanged();
    }

    private void refreshHistory() {
        List<HistoryEntry> entries = controller.getHistory();
        StringBuilder builder = new StringBuilder();
        for (int index = entries.size() - 1; index >= 0 && index >= entries.size() - 30; index--) {
            HistoryEntry entry = entries.get(index);
            String marker =
                    "received".equals(entry.direction) ? getString(R.string.history_received_marker) : getString(R.string.history_sent_marker);
            if (builder.length() > 0) {
                builder.append("\n\n");
            }
            builder.append(getString(R.string.history_format, marker, entry.peerName, entry.text));
        }
        historyText.setText(builder.toString());
    }

    private void pairSelectedPeer() {
        Peer peer = selectedPeer();
        if (peer == null) {
            setStatus(getString(R.string.status_select_device));
            return;
        }
        String pairCode = pairCodeInput.getText().toString().trim();
        if (pairCode.isEmpty()) {
            setStatus(getString(R.string.status_enter_pair_code));
            return;
        }
        try {
            Peer paired = controller.pairWithPeer(peer, pairCode);
            setStatus(getString(R.string.status_paired, paired.name));
            refreshPeerList();
        } catch (Exception exception) {
            setStatus(getString(R.string.status_failed, exception.getMessage()));
        }
    }

    private void sendSelectedText() {
        Peer peer = selectedPeer();
        if (peer == null) {
            setStatus(getString(R.string.status_select_device));
            return;
        }
        String text = messageInput.getText().toString().trim();
        if (text.isEmpty()) {
            setStatus(getString(R.string.status_enter_message));
            return;
        }
        try {
            controller.sendText(peer, text);
            setStatus(getString(R.string.status_sent, peer.name));
            refreshHistory();
        } catch (Exception exception) {
            setStatus(getString(R.string.status_failed, exception.getMessage()));
        }
    }

    private Peer selectedPeer() {
        int position = deviceSpinner.getSelectedItemPosition();
        if (position < 0 || position >= displayedPeers.size()) {
            return null;
        }
        return displayedPeers.get(position);
    }

    private void setStatus(@NonNull String text) {
        statusText.setText(text);
    }

    private void copyToClipboard(String text) {
        if (clipboardManager == null) {
            setStatus(getString(R.string.status_clipboard_unavailable));
            return;
        }
        lastClipboardText = text;
        clipboardManager.setPrimaryClip(ClipData.newPlainText("EchoText", text));
    }

    private String readClipboardText() {
        if (clipboardManager == null || !clipboardManager.hasPrimaryClip()) {
            return "";
        }
        ClipData clip = clipboardManager.getPrimaryClip();
        if (clip == null || clip.getItemCount() == 0) {
            return "";
        }
        CharSequence text = clip.getItemAt(0).coerceToText(this);
        return text == null ? "" : text.toString();
    }

    private int languageIndex(String preference) {
        return switch (preference) {
            case "en" -> 1;
            case "zh" -> 2;
            default -> 0;
        };
    }

    private String formatPeerLabel(Peer peer) {
        String suffix = peer.sharedSecret == null ? "" : getString(R.string.paired_suffix);
        return peer.name + " (" + peer.platform + ") " + peer.host + ":" + peer.port + suffix;
    }
}
