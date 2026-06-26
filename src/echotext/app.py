from __future__ import annotations

import sys
from functools import partial
from pathlib import Path

from kivy.app import App
from kivy.clock import Clock, ClockEvent
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle
from kivy.logger import Logger
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.spinner import Spinner
from kivy.uix.switch import Switch
from kivy.uix.textinput import TextInput
from kivy.utils import platform as kivy_platform

from echotext.assets import window_icon_path
from echotext.desktop_env import diagnose_desktop_environment, select_windows_font
from echotext.i18n import translator
from echotext.models import EnvironmentDiagnosis, HistoryEntry, Peer
from echotext.runtime import EchoTextRuntime
from echotext.settings import SettingsStore
from echotext.transport import TransportError

COLOR_BG = (0.03, 0.07, 0.12, 1.0)
COLOR_SURFACE = (0.07, 0.16, 0.24, 1.0)
COLOR_SURFACE_ALT = (0.10, 0.21, 0.31, 1.0)
COLOR_ACCENT = (0.19, 0.85, 1.0, 1.0)
COLOR_ACCENT_SOFT = (0.10, 0.28, 0.38, 1.0)
COLOR_TEXT = (0.93, 0.97, 1.0, 1.0)
COLOR_TEXT_MUTED = (0.69, 0.78, 0.86, 1.0)
COLOR_WARN = (1.0, 0.74, 0.42, 1.0)
POLL_CLIPBOARD_SECONDS = 0.75
PAIR_CODE_REFRESH_SECONDS = 5.0


class EchoTextApp(App):
    """Kivy application for EchoText."""

    title = "EchoText"

    def build(self) -> BoxLayout:
        """Build the main application surface."""

        self.runtime: EchoTextRuntime | None = None
        self.language_preference = SettingsStore().language()
        self.translate = translator(self.language_preference)
        self.peer_by_label: dict[str, Peer] = {}
        self.language_labels: dict[str, str] = {}
        self.last_clipboard_text = ""
        self.latest_text = ""
        self.selected_peer_id: str | None = None
        self._clipboard_available = True
        self._pair_code_event: ClockEvent | None = None
        self._clipboard_event: ClockEvent | None = None
        self.environment_diagnosis = EnvironmentDiagnosis(True, True, False, "none", "", "")

        Window.clearcolor = COLOR_BG
        icon_path = window_icon_path()
        if icon_path is not None:
            try:
                Window.set_icon(str(icon_path))
            except Exception as exc:
                Logger.warning(f"EchoText failed to set window icon: {exc}")

        root = BoxLayout(orientation="vertical", padding=dp(18), spacing=dp(10))
        self._install_root_background(root)

        self.status_label = Label(
            text="EchoText",
            size_hint_y=None,
            height=dp(34),
            color=COLOR_TEXT,
            bold=True,
            font_size="22sp",
        )
        root.add_widget(self.status_label)

        self.diagnostic_label = Label(
            text="",
            size_hint_y=None,
            height=0,
            color=COLOR_WARN,
            halign="left",
            valign="middle",
            font_size="14sp",
        )
        self.diagnostic_label.bind(texture_size=self._resize_diagnostic_label, width=self._resize_diagnostic_label)
        root.add_widget(self.diagnostic_label)

        self.pair_label = Label(
            size_hint_y=None,
            height=dp(34),
            color=COLOR_TEXT_MUTED,
            font_size="16sp",
        )
        root.add_widget(self.pair_label)

        device_row = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        self.device_spinner = Spinner(text="", values=[], size_hint_x=0.72)
        self._style_spinner(self.device_spinner)
        self.device_spinner.bind(text=self._update_selected_peer_details)
        device_row.add_widget(self.device_spinner)
        self.refresh_button = Button(on_press=self._manual_refresh, size_hint_x=0.28)
        self._style_button(self.refresh_button)
        device_row.add_widget(self.refresh_button)
        root.add_widget(device_row)

        self.peer_detail_label = Label(
            text="",
            size_hint_y=None,
            height=0,
            color=COLOR_TEXT_MUTED,
            halign="left",
            valign="middle",
            font_size="14sp",
        )
        self.peer_detail_label.bind(texture_size=self._resize_peer_detail_label, width=self._resize_peer_detail_label)
        root.add_widget(self.peer_detail_label)

        pair_row = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        self.pair_code_input = TextInput(multiline=False, input_filter="int")
        self._style_text_input(self.pair_code_input)
        pair_row.add_widget(self.pair_code_input)
        self.pair_button = Button(size_hint_x=0.26, on_press=self._pair_selected_peer)
        self._style_button(self.pair_button, accent=True)
        pair_row.add_widget(self.pair_button)
        root.add_widget(pair_row)

        settings_row = BoxLayout(size_hint_y=None, height=dp(54), spacing=dp(10))
        settings_row.add_widget(self._build_toggle_group("auto_sync_label", "auto_sync_switch", self._toggle_auto_sync))
        settings_row.add_widget(
            self._build_toggle_group("history_setting_label", "history_switch", self._toggle_persistent_history)
        )
        root.add_widget(settings_row)

        language_row = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        self.language_label = Label(size_hint_x=0.3, color=COLOR_TEXT_MUTED, font_size="15sp", halign="left")
        self.language_label.bind(size=self._sync_label_text_size)
        language_row.add_widget(self.language_label)
        self.language_spinner = Spinner(text="", values=[], size_hint_x=0.7)
        self._style_spinner(self.language_spinner)
        self.language_spinner.bind(text=self._set_language_preference)
        language_row.add_widget(self.language_spinner)
        root.add_widget(language_row)

        self.message_input = TextInput(multiline=True, size_hint_y=None, height=dp(170))
        self._style_text_input(self.message_input, min_height=dp(170))
        root.add_widget(self.message_input)

        action_row = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        self.paste_button = Button(on_press=self._paste_clipboard)
        self._style_button(self.paste_button)
        action_row.add_widget(self.paste_button)
        self.send_button = Button(on_press=self._send_text)
        self._style_button(self.send_button, accent=True)
        action_row.add_widget(self.send_button)
        self.copy_latest_button = Button(on_press=self._copy_latest)
        self._style_button(self.copy_latest_button)
        action_row.add_widget(self.copy_latest_button)
        self.clear_button = Button(on_press=self._clear_history)
        self._style_button(self.clear_button)
        action_row.add_widget(self.clear_button)
        root.add_widget(action_row)

        self.history_input = TextInput(readonly=True, multiline=True, size_hint_y=1.0, cursor_blink=False)
        self._style_text_input(self.history_input, min_height=dp(220))
        root.add_widget(self.history_input)

        self._apply_translations()
        Clock.schedule_once(self._finish_startup, 0)
        return root

    def on_stop(self) -> None:
        """Stop background services when the app closes."""

        self._stop_scheduled_work()
        if self.runtime is not None:
            self.runtime.stop()

    def on_pause(self) -> bool:
        """Allow Android to pause the app without treating it as a crash."""

        return True

    def _finish_startup(self, _dt: float) -> None:
        self._hide_android_loading_screen()
        try:
            runtime = EchoTextRuntime(
                on_message=self._queue_message,
                on_peer_paired=self._queue_peer_paired,
                on_peers_changed=self._queue_peers_changed,
            )
            runtime.start()
        except Exception as exc:
            Logger.exception("EchoText startup failed")
            self._set_status(f"{self.translate('status_failed')}: {exc}")
            return

        self.runtime = runtime
        self.language_preference = runtime.settings.language()
        self.translate = translator(self.language_preference)
        self.auto_sync_switch.active = runtime.auto_sync_enabled()
        self.history_switch.active = runtime.settings.persistent_history_enabled()
        self._apply_translations()
        self._refresh_environment_diagnosis()
        self._refresh_pair_code()
        self._refresh_peers()
        self._refresh_history()
        self._schedule_pair_code_refresh()
        self._sync_clipboard_timer()
        self._set_status(self.translate("status_ready"))

    def _build_toggle_group(
        self,
        label_attr: str,
        switch_attr: str,
        callback: callable,
    ) -> BoxLayout:
        group = BoxLayout(spacing=dp(10))
        label = Label(color=COLOR_TEXT_MUTED, halign="left", valign="middle", font_size="15sp")
        label.bind(size=self._sync_label_text_size)
        setattr(self, label_attr, label)
        group.add_widget(label)

        toggle = Switch(active=False)
        toggle.bind(active=callback)
        setattr(self, switch_attr, toggle)
        group.add_widget(toggle)
        return group

    def _install_root_background(self, widget: BoxLayout) -> None:
        with widget.canvas.before:
            self._root_bg_color = Color(*COLOR_BG)
            self._root_bg_rect = Rectangle(pos=widget.pos, size=widget.size)
        widget.bind(pos=self._update_root_background, size=self._update_root_background)

    def _update_root_background(self, widget: BoxLayout, *_args: object) -> None:
        self._root_bg_rect.pos = widget.pos
        self._root_bg_rect.size = widget.size

    def _style_button(self, button: Button, accent: bool = False) -> None:
        button.background_normal = ""
        button.background_down = ""
        button.background_disabled_normal = ""
        button.background_disabled_down = ""
        button.background_color = COLOR_ACCENT_SOFT if accent else COLOR_SURFACE_ALT
        button.color = COLOR_TEXT
        button.bold = True
        button.font_size = "15sp"

    def _style_spinner(self, spinner: Spinner) -> None:
        spinner.background_normal = ""
        spinner.background_down = ""
        spinner.background_disabled_normal = ""
        spinner.background_color = COLOR_SURFACE
        spinner.color = COLOR_TEXT
        spinner.sync_height = True
        spinner.font_size = "15sp"

    def _style_text_input(self, text_input: TextInput, min_height: float = dp(48)) -> None:
        text_input.background_normal = ""
        text_input.background_active = ""
        text_input.background_color = COLOR_SURFACE
        text_input.foreground_color = COLOR_TEXT
        text_input.cursor_color = COLOR_ACCENT
        text_input.hint_text_color = COLOR_TEXT_MUTED
        text_input.font_size = "15sp"
        text_input.padding = [dp(12), dp(12), dp(12), dp(12)]
        if text_input.size_hint_y is None:
            text_input.height = max(float(text_input.height), float(min_height))

    def _sync_label_text_size(self, label: Label, *_args: object) -> None:
        label.text_size = (label.width, None)

    def _schedule_pair_code_refresh(self) -> None:
        if self._pair_code_event is None:
            self._pair_code_event = Clock.schedule_interval(self._refresh_pair_code_timer, PAIR_CODE_REFRESH_SECONDS)

    def _refresh_pair_code_timer(self, _dt: float) -> None:
        self._refresh_pair_code()

    def _sync_clipboard_timer(self) -> None:
        if self._clipboard_event is not None:
            self._clipboard_event.cancel()
            self._clipboard_event = None
        if self.runtime is None or not self.runtime.auto_sync_enabled():
            return
        self._clipboard_event = Clock.schedule_interval(self._poll_clipboard_for_sync, POLL_CLIPBOARD_SECONDS)

    def _poll_clipboard_for_sync(self, _dt: float) -> None:
        current = self._clipboard_paste()
        if not current or current == self.last_clipboard_text:
            return
        self.last_clipboard_text = current
        self.message_input.text = current
        self._send_text()

    def _stop_scheduled_work(self) -> None:
        if self._pair_code_event is not None:
            self._pair_code_event.cancel()
            self._pair_code_event = None
        if self._clipboard_event is not None:
            self._clipboard_event.cancel()
            self._clipboard_event = None

    def _manual_refresh(self, *_args: object) -> None:
        self._refresh_environment_diagnosis()
        self._refresh_pair_code()
        self._refresh_peers()

    def _refresh_pair_code(self) -> None:
        if self.runtime is None:
            self.pair_label.text = ""
            return
        identity = self.runtime.identity()
        code = self.runtime.pair_code.code
        text = f"{identity.name} · {identity.host}:{identity.port} · {self.translate('pair_code')}: {code}"
        if self.pair_label.text != text:
            self.pair_label.text = text

    def _queue_peers_changed(self) -> None:
        Clock.schedule_once(self._handle_peers_changed, 0)

    def _handle_peers_changed(self, _dt: float) -> None:
        self._refresh_peers()

    def _refresh_peers(self, *_args: object) -> None:
        if self.runtime is None:
            self.peer_by_label = {}
            self.device_spinner.values = []
            self.device_spinner.text = self.translate("no_devices")
            self.peer_detail_label.text = ""
            return

        previous_peer = self._selected_peer()
        if previous_peer is not None:
            self.selected_peer_id = previous_peer.device_id

        peers = [peer for peer in self.runtime.peers() if peer.device_id != self.runtime.identity().device_id]
        self.peer_by_label = {self._peer_label(peer): peer for peer in peers}
        values = tuple(self.peer_by_label)
        if tuple(self.device_spinner.values) != values:
            self.device_spinner.values = values

        selected_label = None
        if self.selected_peer_id is not None:
            selected_label = next(
                (label for label, peer in self.peer_by_label.items() if peer.device_id == self.selected_peer_id),
                None,
            )
        if selected_label is not None:
            self.device_spinner.text = selected_label
        elif values:
            self.device_spinner.text = values[0]
        else:
            self.device_spinner.text = self.translate("no_devices")
        self._update_selected_peer_details()

    def _pair_selected_peer(self, *_args: object) -> None:
        if self.runtime is None:
            return
        peer = self._selected_peer()
        if peer is None:
            self._set_status(self.translate("status_select_device"))
            return
        pair_code = self.pair_code_input.text.strip()
        if not pair_code:
            self._set_status(self.translate("status_enter_pair_code"))
            return
        try:
            paired = self.runtime.pair_with_peer(peer, pair_code)
        except TransportError as exc:
            self._set_status(f"{self.translate('status_failed')}: {exc}")
            return
        self.selected_peer_id = paired.device_id
        self._set_status(f"{self.translate('status_paired')}: {paired.name}")
        self._refresh_peers()

    def _send_text(self, *_args: object) -> None:
        if self.runtime is None:
            return
        peer = self._selected_peer()
        text = self.message_input.text.strip()
        if peer is None:
            self._set_status(self.translate("status_select_device"))
            return
        if not text:
            self._set_status(self.translate("status_enter_message"))
            return
        try:
            entry = self.runtime.send_text(peer, text)
        except TransportError as exc:
            self._set_status(f"{self.translate('status_failed')}: {exc}")
            return
        self.latest_text = entry.text
        self.last_clipboard_text = entry.text
        self._set_status(f"{self.translate('status_sent')}: {peer.name}")
        self._refresh_history()

    def _paste_clipboard(self, *_args: object) -> None:
        text = self._clipboard_paste()
        if not self._clipboard_available:
            self._set_status(self.translate("status_clipboard_unavailable"))
            return
        if not text:
            self._set_status(self.translate("status_clipboard_empty"))
            return
        self.message_input.text = text

    def _copy_latest(self, *_args: object) -> None:
        if not self.latest_text:
            self._set_status(self.translate("status_nothing_to_copy"))
            return
        self._clipboard_copy(self.latest_text)
        if not self._clipboard_available:
            self._set_status(self.translate("status_clipboard_unavailable"))

    def _clear_history(self, *_args: object) -> None:
        if self.runtime is None:
            return
        self.runtime.clear_history()
        self.latest_text = ""
        self._refresh_history()
        self._set_status(self.translate("status_history_cleared"))

    def _toggle_auto_sync(self, _switch: Switch, active: bool) -> None:
        if self.runtime is None:
            return
        self.runtime.set_auto_sync_enabled(active)
        if not active:
            self.last_clipboard_text = ""
        self._sync_clipboard_timer()

    def _toggle_persistent_history(self, _switch: Switch, active: bool) -> None:
        if self.runtime is None:
            return
        self.runtime.set_persistent_history(active)

    def _queue_message(self, entry: HistoryEntry) -> None:
        Clock.schedule_once(partial(self._handle_received_message, entry), 0)

    def _handle_received_message(self, entry: HistoryEntry, _dt: float) -> None:
        self.latest_text = entry.text
        self.last_clipboard_text = entry.text
        self._clipboard_copy(entry.text)
        self._refresh_history()

    def _queue_peer_paired(self, peer: Peer) -> None:
        Clock.schedule_once(partial(self._handle_peer_paired, peer), 0)

    def _handle_peer_paired(self, peer: Peer, _dt: float) -> None:
        self.selected_peer_id = peer.device_id
        self._set_status(f"{self.translate('status_paired')}: {peer.name}")
        self._refresh_peers()

    def _refresh_history(self) -> None:
        if self.runtime is None:
            self.history_input.text = ""
            return
        lines = []
        for entry in reversed(self.runtime.history.entries[-30:]):
            direction = "<<" if entry.direction == "received" else ">>"
            lines.append(f"{direction} {entry.peer_name}: {entry.text}")
        self.history_input.text = "\n\n".join(lines)
        self.history_input.cursor = (0, 0)

    def _resize_diagnostic_label(self, label: Label, *_args: object) -> None:
        label.text_size = (label.width, None)
        label.texture_update()
        label.height = 0 if not label.text else max(dp(32), label.texture_size[1] + dp(10))

    def _resize_peer_detail_label(self, label: Label, *_args: object) -> None:
        label.text_size = (label.width, None)
        label.texture_update()
        label.height = 0 if not label.text else max(dp(24), label.texture_size[1] + dp(8))

    def _set_status(self, text: str) -> None:
        self.status_label.text = text

    def _selected_peer(self) -> Peer | None:
        return self.peer_by_label.get(self.device_spinner.text)

    def _update_selected_peer_details(self, *_args: object) -> None:
        peer = self._selected_peer()
        if peer is None:
            self.peer_detail_label.text = ""
            return
        self.selected_peer_id = peer.device_id
        paired = self.translate("paired_suffix") if peer.shared_secret else ""
        self.peer_detail_label.text = f"{peer.name} · {peer.host}:{peer.port} · {peer.platform}{paired}"

    def _set_language_preference(self, _spinner: Spinner, label: str) -> None:
        code = next((key for key, value in self.language_labels.items() if value == label), None)
        if code is None or code == self.language_preference:
            return
        self.language_preference = code
        if self.runtime is not None:
            self.runtime.settings.set_language(code)
        self.translate = translator(code)
        self._apply_translations()
        self._refresh_environment_diagnosis()
        self._refresh_pair_code()
        self._refresh_peers()
        self._refresh_history()
        self._set_status(self.translate("status_ready"))

    def _apply_translations(self) -> None:
        self.title = self.translate("title")
        self.refresh_button.text = self.translate("refresh")
        self.pair_button.text = self.translate("pair")
        self.pair_code_input.hint_text = self.translate("pair_code_hint")
        self.auto_sync_label.text = self.translate("auto_sync")
        self.history_setting_label.text = self.translate("persistent_history")
        self.language_label.text = self.translate("language")
        self.message_input.hint_text = self.translate("message")
        self.paste_button.text = self.translate("paste")
        self.send_button.text = self.translate("send")
        self.copy_latest_button.text = self.translate("copy_latest")
        self.clear_button.text = self.translate("clear")
        self.language_labels = {
            "auto": self.translate("language_auto"),
            "en": self.translate("language_english"),
            "zh": self.translate("language_chinese"),
        }
        self.language_spinner.values = tuple(self.language_labels.values())
        self.language_spinner.text = self.language_labels.get(self.language_preference, self.language_labels["auto"])
        if not self.device_spinner.values:
            self.device_spinner.text = self.translate("no_devices")
        self._render_environment_diagnosis()

    def _refresh_environment_diagnosis(self) -> None:
        if self.runtime is None:
            return
        if sys.platform != "win32":
            self.environment_diagnosis = EnvironmentDiagnosis(True, True, True, "none", "", "")
            self._render_environment_diagnosis()
            return
        font_ok = kivy_platform == "android" or select_windows_font() is not None
        self.environment_diagnosis = diagnose_desktop_environment(
            self.runtime.identity().host,
            font_ok=font_ok,
            executable=Path(sys.executable),
        )
        self._render_environment_diagnosis()

    def _render_environment_diagnosis(self) -> None:
        warning_key = self.environment_diagnosis.warning_key
        if not warning_key:
            self.diagnostic_label.text = ""
            self.diagnostic_label.height = 0
            return
        template = self.translate(warning_key)
        detail = self.environment_diagnosis.warning_detail
        self.diagnostic_label.text = template.format(detail=detail)
        self._resize_diagnostic_label(self.diagnostic_label)

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

    def _peer_label(self, peer: Peer) -> str:
        if len(peer.name) <= 24:
            return peer.name
        return f"{peer.name[:21]}..."
