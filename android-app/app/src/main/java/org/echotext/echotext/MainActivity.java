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
import java.util.Objects;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import org.echotext.echotext.core.EchoTextController;
import org.echotext.echotext.core.FailureStatusMapper;
import org.echotext.echotext.core.SettingsStore;
import org.echotext.echotext.model.HistoryEntry;
import org.echotext.echotext.model.Peer;
import org.echotext.echotext.ui.LocaleHelper;

public class MainActivity extends AppCompatActivity implements EchoTextController.Listener {
    private static final long PAIR_CODE_REFRESH_MILLIS = 5_000L;

    private final Handler handler = new Handler(Looper.getMainLooper());
    private final ExecutorService requestExecutor = Executors.newSingleThreadExecutor();
    private final Runnable pairCodeRefreshRunnable =
            new Runnable() {
                @Override
                public void run() {
                    refreshPairCode();
                    handler.postDelayed(this, PAIR_CODE_REFRESH_MILLIS);
                }
            };

    private EchoTextController controller;
    private ClipboardManager clipboardManager;
    private ClipboardManager.OnPrimaryClipChangedListener clipboardListener;

    private TextView statusText;
    private TextView pairCodeText;
    private TextView peerDetailText;
    private Spinner deviceSpinner;
    private Spinner languageSpinner;
    private EditText pairCodeInput;
    private EditText messageInput;
    private SwitchCompat autoSyncSwitch;
    private SwitchCompat persistentHistorySwitch;
    private TextView historyText;
    private Button pairButton;
    private Button sendButton;

    private ArrayAdapter<String> deviceAdapter;
    private ArrayAdapter<String> languageAdapter;
    private final List<Peer> displayedPeers = new ArrayList<>();
    private final List<String> displayedPeerLabels = new ArrayList<>();
    private boolean suppressLanguageSelection;
    private boolean suppressToggleCallbacks;
    private String lastClipboardText = "";
    private String selectedPeerDeviceId;

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
        refreshUi();
        setStatus(getString(R.string.status_ready));
    }

    @Override
    protected void onResume() {
        super.onResume();
        controller.addListener(this);
        if (clipboardManager != null) {
            clipboardManager.addPrimaryClipChangedListener(clipboardListener);
        }
        refreshToggles();
        refreshUi();
        handler.post(pairCodeRefreshRunnable);
    }

    @Override
    protected void onPause() {
        super.onPause();
        controller.removeListener(this);
        if (clipboardManager != null) {
            clipboardManager.removePrimaryClipChangedListener(clipboardListener);
        }
        handler.removeCallbacks(pairCodeRefreshRunnable);
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        requestExecutor.shutdownNow();
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
        selectedPeerDeviceId = peer.deviceId;
        setStatus(getString(R.string.status_paired, peer.name));
        refreshPeerList();
    }

    private void bindViews() {
        statusText = findViewById(R.id.status_text);
        pairCodeText = findViewById(R.id.pair_code_text);
        peerDetailText = findViewById(R.id.peer_detail_text);
        deviceSpinner = findViewById(R.id.device_spinner);
        languageSpinner = findViewById(R.id.language_spinner);
        pairCodeInput = findViewById(R.id.pair_code_input);
        messageInput = findViewById(R.id.message_input);
        autoSyncSwitch = findViewById(R.id.auto_sync_switch);
        persistentHistorySwitch = findViewById(R.id.persistent_history_switch);
        historyText = findViewById(R.id.history_text);
        pairButton = findViewById(R.id.pair_button);
        sendButton = findViewById(R.id.send_button);

        deviceAdapter = new ArrayAdapter<>(this, android.R.layout.simple_spinner_item, new ArrayList<>());
        deviceAdapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        deviceSpinner.setAdapter(deviceAdapter);
        deviceSpinner.setOnItemSelectedListener(new android.widget.AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(android.widget.AdapterView<?> parent, android.view.View view, int position, long id) {
                Peer peer = selectedPeer();
                selectedPeerDeviceId = peer == null ? null : peer.deviceId;
                updateSelectedPeerDetails();
            }

            @Override
            public void onNothingSelected(android.widget.AdapterView<?> parent) {
                updateSelectedPeerDetails();
            }
        });
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
        Button pasteButton = findViewById(R.id.paste_button);
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
        autoSyncSwitch.setOnCheckedChangeListener((buttonView, isChecked) -> {
            if (!suppressToggleCallbacks) {
                controller.setAutoSyncEnabled(isChecked);
            }
        });
        persistentHistorySwitch.setOnCheckedChangeListener((buttonView, isChecked) -> {
            if (!suppressToggleCallbacks) {
                controller.setPersistentHistory(isChecked);
            }
        });
    }

    private void refreshUi() {
        refreshPairCode();
        refreshPeerList();
        refreshHistory();
    }

    private void refreshToggles() {
        suppressToggleCallbacks = true;
        autoSyncSwitch.setChecked(controller.isAutoSyncEnabled());
        persistentHistorySwitch.setChecked(controller.isPersistentHistoryEnabled());
        suppressToggleCallbacks = false;
    }

    private void refreshPairCode() {
        org.echotext.echotext.model.DeviceIdentity identity = controller.getIdentity();
        if (identity == null) {
            return;
        }
        pairCodeText.setText(
                getString(R.string.pair_code_display, identity.name, identity.host, identity.port, controller.getPairCode()));
    }

    private void refreshPeerList() {
        List<Peer> peers = controller.getPeers();
        String desiredDeviceId = selectedPeerDeviceId;
        Peer currentlySelected = selectedPeer();
        if (currentlySelected != null) {
            desiredDeviceId = currentlySelected.deviceId;
        }

        if (!samePeerPresentation(peers, displayedPeers)) {
            displayedPeers.clear();
            displayedPeers.addAll(peers);
            displayedPeerLabels.clear();
            deviceAdapter.clear();
            for (Peer peer : peers) {
                String label = formatPeerLabel(peer);
                displayedPeerLabels.add(label);
                deviceAdapter.add(label);
            }
            deviceAdapter.notifyDataSetChanged();
        }

        if (peers.isEmpty()) {
            selectedPeerDeviceId = null;
            deviceSpinner.setEnabled(false);
            if (deviceAdapter.getCount() == 0) {
                deviceAdapter.add(getString(R.string.no_devices));
                deviceAdapter.notifyDataSetChanged();
            }
            deviceSpinner.setSelection(0);
            updateSelectedPeerDetails();
            return;
        }

        deviceSpinner.setEnabled(true);
        int selectedIndex = indexOfDeviceId(desiredDeviceId);
        if (selectedIndex < 0) {
            selectedIndex = 0;
        }
        deviceSpinner.setSelection(selectedIndex, false);
        Peer selected = selectedPeer();
        selectedPeerDeviceId = selected == null ? null : selected.deviceId;
        updateSelectedPeerDetails();
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
        setRequestButtonsEnabled(false);
        requestExecutor.execute(() -> {
            try {
                Peer paired = controller.pairWithPeer(peer, pairCode);
                handler.post(() -> {
                    selectedPeerDeviceId = paired.deviceId;
                    setStatus(getString(R.string.status_paired, paired.name));
                    refreshPeerList();
                    setRequestButtonsEnabled(true);
                });
            } catch (Exception exception) {
                handler.post(() -> {
                    setStatus(statusTextForException(exception, peer));
                    setRequestButtonsEnabled(true);
                });
            }
        });
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
        selectedPeerDeviceId = peer.deviceId;
        setRequestButtonsEnabled(false);
        requestExecutor.execute(() -> {
            try {
                controller.sendText(peer, text);
                handler.post(() -> {
                    setStatus(getString(R.string.status_sent, peer.name));
                    refreshHistory();
                    setRequestButtonsEnabled(true);
                });
            } catch (Exception exception) {
                handler.post(() -> {
                    setStatus(statusTextForException(exception, peer));
                    setRequestButtonsEnabled(true);
                });
            }
        });
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

    private void setRequestButtonsEnabled(boolean enabled) {
        pairButton.setEnabled(enabled);
        sendButton.setEnabled(enabled);
    }

    private String statusTextForException(Exception exception, Peer peer) {
        int stringRes = FailureStatusMapper.stringResFor(exception, peer);
        String message = getString(stringRes);
        if (stringRes == R.string.status_request_failed && exception.getMessage() != null && !exception.getMessage().isBlank()) {
            return getString(R.string.status_failed, exception.getMessage());
        }
        return message;
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

    private void updateSelectedPeerDetails() {
        Peer peer = selectedPeer();
        if (peer == null) {
            peerDetailText.setText("");
            return;
        }
        String suffix = peer.sharedSecret == null ? "" : getString(R.string.paired_suffix);
        peerDetailText.setText(peer.name + " · " + peer.host + ":" + peer.port + " · " + peer.platform + suffix);
    }

    private String formatPeerLabel(Peer peer) {
        if (peer.name.length() <= 24) {
            return peer.name;
        }
        return peer.name.substring(0, 21) + "...";
    }

    private boolean samePeerPresentation(List<Peer> first, List<Peer> second) {
        if (first.size() != second.size()) {
            return false;
        }
        for (int index = 0; index < first.size(); index++) {
            Peer left = first.get(index);
            Peer right = second.get(index);
            if (!Objects.equals(left.deviceId, right.deviceId)
                    || !Objects.equals(left.name, right.name)
                    || !Objects.equals(left.platform, right.platform)
                    || !Objects.equals(left.host, right.host)
                    || left.port != right.port
                    || !Objects.equals(left.sharedSecret, right.sharedSecret)) {
                return false;
            }
        }
        return true;
    }

    private int indexOfDeviceId(String deviceId) {
        if (deviceId == null) {
            return -1;
        }
        for (int index = 0; index < displayedPeers.size(); index++) {
            if (deviceId.equals(displayedPeers.get(index).deviceId)) {
                return index;
            }
        }
        return -1;
    }
}
