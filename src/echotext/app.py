from __future__ import annotations

from functools import partial

from kivy.app import App
from kivy.clock import Clock
from kivy.logger import Logger
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.switch import Switch
from kivy.uix.textinput import TextInput
from kivy.utils import platform as kivy_platform

from echotext.i18n import translator
from echotext.models import HistoryEntry, Peer
from echotext.runtime import EchoTextRuntime
from echotext.transport import TransportError


class EchoTextApp(App):
    """Kivy application for EchoText."""

    title = "EchoText"

    def build(self) -> BoxLayout:
        """Build the main application surface."""

        self.runtime: EchoTextRuntime | None = None
        self.translate = translator("auto")
        self.peer_by_label: dict[str, Peer] = {}
        self.last_clipboard_text = ""
        self.latest_text = ""
        self._clipboard_available = True

        root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))

        self.status_label = Label(text="EchoText", size_hint_y=None, height=dp(28))
        root.add_widget(self.status_label)

        self.pair_label = Label(size_hint_y=None, height=dp(36))
        root.add_widget(self.pair_label)

        device_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        self.device_spinner = Spinner(text="", values=[], size_hint_x=0.65)
        device_row.add_widget(self.device_spinner)
        self.refresh_button = Button(on_press=self._refresh_peers)
        device_row.add_widget(self.refresh_button)
        root.add_widget(device_row)

        pair_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        self.pair_code_input = TextInput(multiline=False, input_filter="int")
        pair_row.add_widget(self.pair_code_input)
        self.pair_button = Button(size_hint_x=0.35, on_press=self._pair_selected_peer)
        pair_row.add_widget(self.pair_button)
        root.add_widget(pair_row)

        settings_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        self.auto_sync_label = Label()
        settings_row.add_widget(self.auto_sync_label)
        self.auto_sync_switch = Switch(active=False)
        settings_row.add_widget(self.auto_sync_switch)
        self.history_setting_label = Label()
        settings_row.add_widget(self.history_setting_label)
        self.history_switch = Switch(active=False)
        self.history_switch.bind(active=self._toggle_persistent_history)
        settings_row.add_widget(self.history_switch)
        root.add_widget(settings_row)

        self.message_input = TextInput(multiline=True, size_hint_y=0.3)
        root.add_widget(self.message_input)

        action_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        self.paste_button = Button(on_press=self._paste_clipboard)
        action_row.add_widget(self.paste_button)
        self.send_button = Button(on_press=self._send_text)
        action_row.add_widget(self.send_button)
        self.copy_latest_button = Button(on_press=self._copy_latest)
        action_row.add_widget(self.copy_latest_button)
        self.clear_button = Button(on_press=self._clear_history)
        action_row.add_widget(self.clear_button)
        root.add_widget(action_row)

        self.history_label = Label(text="", markup=False, size_hint_y=None, halign="left", valign="top")
        self.history_label.bind(texture_size=self._resize_history_label)
        history_scroll = ScrollView(size_hint_y=0.45)
        history_scroll.add_widget(self.history_label)
        root.add_widget(history_scroll)

        self._apply_translations()
        Clock.schedule_once(self._finish_startup, 0)
        Clock.schedule_interval(self._tick, 1)
        return root

    def on_stop(self) -> None:
        """Stop background services when the app closes."""

        if self.runtime is not None:
            self.runtime.stop()

    def on_pause(self) -> bool:
        """Allow Android to pause the app without treating it as a crash."""

        return True

    def _finish_startup(self, _dt: float) -> None:
        self._hide_android_loading_screen()
        try:
            runtime = EchoTextRuntime(on_message=self._queue_message, on_peer_paired=self._queue_peer_paired)
            runtime.start()
        except Exception as exc:
            Logger.exception("EchoText startup failed")
            self._set_status(f"{self.translate('status_failed')}: {exc}")
            return

        self.runtime = runtime
        self.translate = translator(self.runtime.settings.language())
        self.history_switch.active = self.runtime.settings.persistent_history_enabled()
        self._apply_translations()
        self._refresh_pair_code()
        self._refresh_peers()
        self._refresh_history()
        self._set_status(self.translate("status_ready"))

    def _tick(self, _dt: float) -> None:
        if self.runtime is None:
            return
        self._refresh_pair_code()
        self._refresh_peers()
        if self.auto_sync_switch.active:
            current = self._clipboard_paste()
            if current and current != self.last_clipboard_text:
                self.last_clipboard_text = current
                self.message_input.text = current
                self._send_text()

    def _refresh_pair_code(self) -> None:
        if self.runtime is None:
            self.pair_label.text = ""
            return
        identity = self.runtime.identity()
        code = self.runtime.pair_code.code
        self.pair_label.text = (
            f"{identity.name} · {identity.host}:{identity.port} · {self.translate('pair_code')}: {code}"
        )

    def _refresh_peers(self, *_args: object) -> None:
        if self.runtime is None:
            self.device_spinner.values = []
            self.device_spinner.text = self.translate("no_devices")
            return
        peers = self.runtime.peers()
        self.peer_by_label = {
            self._peer_label(peer): peer for peer in peers if peer.device_id != self.runtime.identity().device_id
        }
        values = list(self.peer_by_label)
        self.device_spinner.values = values
        if values and self.device_spinner.text not in values:
            self.device_spinner.text = values[0]
        if not values:
            self.device_spinner.text = self.translate("no_devices")

    def _pair_selected_peer(self, *_args: object) -> None:
        if self.runtime is None:
            return
        peer = self._selected_peer()
        if peer is None:
            return
        try:
            paired = self.runtime.pair_with_peer(peer, self.pair_code_input.text)
        except TransportError as exc:
            self._set_status(f"{self.translate('status_failed')}: {exc}")
            return
        self._set_status(f"{self.translate('status_paired')}: {paired.name}")
        self._refresh_peers()

    def _send_text(self, *_args: object) -> None:
        if self.runtime is None:
            return
        peer = self._selected_peer()
        text = self.message_input.text.strip()
        if peer is None or not text:
            return
        try:
            entry = self.runtime.send_text(peer, text)
        except TransportError as exc:
            self._set_status(f"{self.translate('status_failed')}: {exc}")
            return
        self.latest_text = entry.text
        self._set_status(f"{self.translate('status_sent')}: {peer.name}")
        self._refresh_history()

    def _paste_clipboard(self, *_args: object) -> None:
        self.message_input.text = self._clipboard_paste()

    def _copy_latest(self, *_args: object) -> None:
        if self.latest_text:
            self._clipboard_copy(self.latest_text)

    def _clear_history(self, *_args: object) -> None:
        if self.runtime is None:
            return
        self.runtime.clear_history()
        self.latest_text = ""
        self._refresh_history()

    def _toggle_persistent_history(self, _switch: Switch, active: bool) -> None:
        if self.runtime is None:
            return
        self.runtime.set_persistent_history(active)

    def _queue_message(self, entry: HistoryEntry) -> None:
        Clock.schedule_once(partial(self._handle_received_message, entry), 0)

    def _handle_received_message(self, entry: HistoryEntry, _dt: float) -> None:
        self.latest_text = entry.text
        self._clipboard_copy(entry.text)
        self._refresh_history()

    def _queue_peer_paired(self, peer: Peer) -> None:
        Clock.schedule_once(partial(self._handle_peer_paired, peer), 0)

    def _handle_peer_paired(self, peer: Peer, _dt: float) -> None:
        self._set_status(f"{self.translate('status_paired')}: {peer.name}")
        self._refresh_peers()

    def _refresh_history(self) -> None:
        if self.runtime is None:
            self.history_label.text = ""
            return
        lines = []
        for entry in reversed(self.runtime.history.entries[-30:]):
            direction = "<<" if entry.direction == "received" else ">>"
            lines.append(f"{direction} {entry.peer_name}: {entry.text}")
        self.history_label.text = "\n\n".join(lines)

    def _resize_history_label(self, label: Label, texture_size: tuple[int, int]) -> None:
        label.text_size = (label.width, None)
        label.height = max(dp(120), texture_size[1] + dp(16))

    def _set_status(self, text: str) -> None:
        self.status_label.text = text

    def _selected_peer(self) -> Peer | None:
        return self.peer_by_label.get(self.device_spinner.text)

    def _apply_translations(self) -> None:
        self.title = self.translate("title")
        self.refresh_button.text = self.translate("refresh")
        self.pair_button.text = self.translate("pair")
        self.pair_code_input.hint_text = self.translate("pair_code_hint")
        self.auto_sync_label.text = self.translate("auto_sync")
        self.history_setting_label.text = self.translate("persistent_history")
        self.message_input.hint_text = self.translate("message")
        self.paste_button.text = self.translate("paste")
        self.send_button.text = self.translate("send")
        self.copy_latest_button.text = self.translate("copy_latest")
        self.clear_button.text = self.translate("clear")
        if not self.device_spinner.values:
            self.device_spinner.text = self.translate("no_devices")

    def _clipboard_paste(self) -> str:
        if not self._clipboard_available:
            return ""
        try:
            from kivy.core.clipboard import Clipboard

            return str(Clipboard.paste() or "")
        except Exception as exc:
            self._clipboard_available = False
            Logger.warning(f"EchoText clipboard paste failed: {exc}")
            return ""

    def _clipboard_copy(self, text: str) -> None:
        if not self._clipboard_available:
            return
        try:
            from kivy.core.clipboard import Clipboard

            Clipboard.copy(text)
        except Exception as exc:
            self._clipboard_available = False
            Logger.warning(f"EchoText clipboard copy failed: {exc}")

    def _hide_android_loading_screen(self) -> None:
        if kivy_platform != "android":
            return
        try:
            from android import loadingscreen

            loadingscreen.hide_loading_screen()
        except Exception as exc:
            Logger.warning(f"EchoText failed to hide Android loading screen: {exc}")

    @staticmethod
    def _peer_label(peer: Peer) -> str:
        paired = " · paired" if peer.shared_secret else ""
        return f"{peer.name} ({peer.platform}) {peer.host}:{peer.port}{paired}"
