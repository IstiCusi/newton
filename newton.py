#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Keylight Tray (i3)
A small PyQt5 tray app to control multiple Elgato Key Lights by static IPs.
- Shows a tray icon (works nicely with i3 + a system tray)
- One compact window with:
  - On/Off button
  - Brightness slider (0–100)
  - Color temperature slider (Kelvin 2900–7000)
  - Search button to probe all configured IPs
  - LED indicator (green = all reachable, red = one or more unreachable)
- All lamps are controlled together (broadcast same settings to all IPs).

Dependencies (Arch/EndeavourOS):
  sudo pacman -S python-requests python-pyqt5
Run:
  python keylight_tray.py

Customize the IPs by editing the STATIC_IPS list below.
"""

import sys
import threading
from dataclasses import dataclass, field
from typing import Dict, Optional

import requests
from PyQt5 import QtCore, QtGui, QtWidgets
from requests.exceptions import RequestException

# ---------------------- User configuration ----------------------
# Put your known lamp IPs here. You can add/remove IPs anytime.
STATIC_IPS = [
    "192.168.0.83",
    "192.168.0.181",
]
# Request timeouts (seconds)
HTTP_TIMEOUT = 1.2
# ---------------------------------------------------------------

API_PATH = "/elgato/lights"


def kelvin_to_mired(k: int) -> int:
    """Convert Kelvin (approx 2900–7000) to mired used by Key Light API."""
    k = max(2900, min(7000, int(k)))
    return int(round(1_000_000 / k))


def clamp_brightness(b: int) -> int:
    """ Establish range in percentage (0-100) of brightness values"""
    return max(0, min(100, int(b)))


@dataclass
class LightStatus:
    """ Data class containing lamp data """
    reachable: bool
    on: int = 0
    brightness: int = 0
    mired: int = 0
    raw: dict = field(default_factory=dict)


class KeylightHTTP:
    """
    Simple HTTP client for controlling an Elgato Key Light by IP address.

    This class provides methods to query and update the state of a Key Light
    device via its local REST API. It supports reading the current status
    (on/off, brightness, temperature) and sending commands to change them.

    Attributes
    ----------
    host : str
        The IP address of the Key Light.
    base : str
        The full base URL for the Key Light API endpoint.

    Methods
    -------
    get() -> LightStatus
        Fetch the current status of the light. Returns a LightStatus object.
    set(on: Optional[int] = None, brightness: Optional[int] = None,
        mired: Optional[int] = None) -> bool
        Update the light's state. Only the provided parameters are changed.
        Returns True if the request succeeded, otherwise False.
    """

    def __init__(self, host: str):
        self.host = host
        self.base = f"http://{host}:9123{API_PATH}"

    def get(self) -> LightStatus:
        """ Get the LightStatus"""
        try:
            r = requests.get(self.base, timeout=HTTP_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            lights = data.get("lights", [])
            if not lights:
                return LightStatus(reachable=True, raw=data)
            l0 = lights[0]
            return LightStatus(
                reachable=True,
                on=int(l0.get("on", 0)),
                brightness=int(l0.get("brightness", 0)),
                mired=int(l0.get("temperature", 0)),
                raw=data,
            )
        except RequestException:
            return LightStatus(reachable=False)

    def set(self, on: Optional[int] = None,
            brightness: Optional[int] = None, mired: Optional[int] = None) -> bool:
        """ Set the light status by attributes and gives back False if failing to do so """

        payload = {"numberOfLights": 1, "lights": [{}]}
        if on is not None:
            payload["lights"][0]["on"] = 1 if on else 0
        if brightness is not None:
            payload["lights"][0]["brightness"] = clamp_brightness(brightness)
        if mired is not None:
            payload["lights"][0]["temperature"] = int(mired)
        try:
            r = requests.put(self.base, json=payload, timeout=HTTP_TIMEOUT)
            r.raise_for_status()
            return True
        except RequestException:
            return False


class RoundLED(QtWidgets.QLabel):
    """A small round LED indicator (green/red)."""

    def __init__(self, diameter=14, parent=None):
        super().__init__(parent)
        self._diameter = diameter
        self._color = QtGui.QColor("red")
        self.setFixedSize(diameter, diameter)

    def set_color(self, color_name: str):
        """ Set the Color value"""
        self._color = QtGui.QColor(color_name)
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)
        brush = QtGui.QBrush(self._color)
        painter.setBrush(brush)
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawEllipse(rect)


class ControlWindow(QtWidgets.QWidget):
    request_apply = QtCore.pyqtSignal(dict)  # {'on':0/1, 'b':0-100, 'k':kelvin or None}
    request_probe = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Keylight Tray")
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        self.setFixedWidth(360)

        # Widgets
        self.led = RoundLED(14)
        self.led.setToolTip("Drücke Suchen, um die IPs zu prüfen")

        self.btn_search = QtWidgets.QPushButton()
        self.btn_search.setToolTip("Lampen suchen (IPs prüfen)")
        self.btn_search.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_BrowserReload))

        self.btn_power = QtWidgets.QPushButton("Aus")
        self.btn_power.setCheckable(True)
        self.btn_power.setToolTip("Ein/Aus für alle Lampen")

        self.sld_b = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.sld_b.setRange(0, 100)
        self.sld_b.setValue(50)
        self.lbl_b = QtWidgets.QLabel("Helligkeit: 50%")

        self.sld_k = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.sld_k.setRange(2900, 7000)
        self.sld_k.setValue(4000)
        self.lbl_k = QtWidgets.QLabel("Farbtemp: 4000 K")

        # Layout
        top = QtWidgets.QHBoxLayout()
        top.addWidget(self.led)
        top.addWidget(self.btn_search)
        top.addStretch(1)
        top.addWidget(self.btn_power)

        v = QtWidgets.QVBoxLayout(self)
        v.addLayout(top)
        v.addWidget(self.lbl_b)
        v.addWidget(self.sld_b)
        v.addWidget(self.lbl_k)
        v.addWidget(self.sld_k)

        # Signals
        self.btn_search.clicked.connect(self.request_probe)
        self.btn_power.toggled.connect(self._power_toggled)
        self.sld_b.valueChanged.connect(self._brightness_changed)
        self.sld_k.valueChanged.connect(self._kelvin_changed)

        # Debounce timers
        self._apply_timer = QtCore.QTimer(self)
        self._apply_timer.setInterval(200)
        self._apply_timer.setSingleShot(True)
        self._apply_timer.timeout.connect(self._emit_apply)

        self._pending = {"on": None, "b": 50, "k": 4000}

    # --- UI callbacks
    def _power_toggled(self, checked: bool):
        self.btn_power.setText("Ein" if checked else "Aus")
        self._pending["on"] = 1 if checked else 0
        self._apply_timer.start()

    def _brightness_changed(self, val: int):
        self.lbl_b.setText(f"Helligkeit: {val}%")
        self._pending["b"] = val
        self._apply_timer.start()

    def _kelvin_changed(self, val: int):
        self.lbl_k.setText(f"Farbtemp: {val} K")
        self._pending["k"] = val
        self._apply_timer.start()

    def _emit_apply(self):
        self.request_apply.emit(dict(self._pending))

    # External updates
    @QtCore.pyqtSlot(bool, str)
    def set_led_state(self, all_ok: bool, tooltip: str = ""):
        self.led.set_color("green" if all_ok else "red")
        if tooltip:
            self.led.setToolTip(tooltip)


class TrayApp(QtWidgets.QSystemTrayIcon):
    def __init__(self, app: QtWidgets.QApplication):
        # Robust icon setup (fallback if theme has no lightbulb icon)
        icon = QtGui.QIcon.fromTheme("lightbulb")
        if icon.isNull():
            # Fallback to a standard icon so QSystemTrayIcon always has one
            style = app.style()
            icon = style.standardIcon(QtWidgets.QStyle.SP_TitleBarMenuButton)
        super().__init__(icon, app)
        self.setToolTip("Keylight Tray")
        self.menu = QtWidgets.QMenu()

        self.action_show = self.menu.addAction("Öffnen/Schließen")
        self.action_quit = self.menu.addAction("Beenden")
        self.setContextMenu(self.menu)

        self.win = ControlWindow()
        self.win.request_apply.connect(self.apply_to_all)
        self.win.request_probe.connect(self.probe_all)

        self.action_show.triggered.connect(self.toggle_window)
        self.action_quit.triggered.connect(QtWidgets.QApplication.quit)
        self.activated.connect(self._on_tray_activated)

        # Networking state
        self.controllers = [KeylightHTTP(ip) for ip in STATIC_IPS]
        self.last_probe: Dict[str, LightStatus] = {}

        # Initial probe (async)
        QtCore.QTimer.singleShot(100, self.probe_all)

    # --- UI actions
    def toggle_window(self):
        if self.win.isVisible():
            self.win.hide()
        else:
            # Position near mouse for convenience
            cursor_pos = QtGui.QCursor.pos()
            self.win.move(cursor_pos.x() - 180, cursor_pos.y() + 10)
            self.win.show()
            self.win.raise_()
            self.win.activateWindow()

    def _on_tray_activated(self, reason):
        if reason == QtWidgets.QSystemTrayIcon.Trigger:
            self.toggle_window()

    # --- Network ops (threaded)
    def probe_all(self):
        def worker():
            statuses: Dict[str, LightStatus] = {}
            tooltip_lines = []
            all_ok = True
            for ctl in self.controllers:
                st = ctl.get()
                statuses[ctl.host] = st
                ok = "OK" if st.reachable else "X"
                tooltip_lines.append(f"{ctl.host}: {'reachable' if st.reachable else 'unreachable'}")
                if not st.reachable:
                    all_ok = False
            self.last_probe = statuses
            tooltip = "\n".join(tooltip_lines)
            # update UI in main thread
            QtCore.QMetaObject.invokeMethod(
                self.win,
                "set_led_state",
                QtCore.Qt.QueuedConnection,
                QtCore.Q_ARG(bool, all_ok),
                QtCore.Q_ARG(str, tooltip),
            )
        threading.Thread(target=worker, daemon=True).start()

    def apply_to_all(self, payload: dict):
        # Convert payload to API format
        on = payload.get("on")
        b = payload.get("b")
        k = payload.get("k")
        mired = kelvin_to_mired(k) if k is not None else None

        def worker():
            for ctl in self.controllers:
                ctl.set(on=on, brightness=b, mired=mired)
        threading.Thread(target=worker, daemon=True).start()


def main():
    app = QtWidgets.QApplication(sys.argv)
    tray = TrayApp(app)
    tray.show()

    # Some panels require the window to be created before showing tray
    # We keep it hidden until clicked.
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
