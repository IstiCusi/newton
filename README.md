# Newton Keylight Tray (i3)

A small **PyQt5 system tray app** to control multiple **Elgato Key Lights** via static IPs.
Designed to work nicely with i3 or any window manager that provides a system tray.

## Features

- System tray icon
- Compact control window with:
  - **On/Off button** (toggles all lights together)
  - **Brightness slider** (0–100%)
  - **Color temperature slider** (Kelvin 2900–7000)
  - **Search button** to probe all configured IPs
  - **LED indicator**:
    - Green = all lights reachable
    - Red = one or more lights unreachable
- Broadcast control — all configured lights receive the same settings

## Installation (EndeavourOS / Arch Linux)

Install dependencies:

```bash
sudo pacman -S python-requests python-pyqt5
```

## Usage

1. Clone or download this repository.
2. Edit the list of static IPs in `keylight_tray.py`:

   ```python
   STATIC_IPS = [
       "192.168.0.83",
       "192.168.0.181",
   ]
   ```

3. Run the app:

   ```bash
   python keylight_tray.py
   ```

The tray icon will appear; click it to open the control window.

## Notes

- The app sends the same brightness, temperature, and on/off state to **all listed IPs**.
- If you add new lamps, just edit the `STATIC_IPS` list and restart.
- Works best in lightweight WMs (like i3), but should also run under KDE, GNOME, XFCE, etc.

---

⚡ Simple, fast, and designed for quick access to your Elgato Key Lights.
