"""
wifi_switcher.py
Controls WiFi connections cross-platform:
  - Windows: uses 'netsh wlan' commands with XML profiles
  - Linux (Ubuntu / Raspberry Pi OS): uses 'nmcli' (NetworkManager)

Switches between ISP SSIDs and verifies connectivity before returning.
"""

import os
import sys
import subprocess
import time
import socket
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

CONNECT_TIMEOUT_SECONDS = 30
CONNECTIVITY_CHECK_HOST = "8.8.8.8"
CONNECTIVITY_CHECK_PORT = 53

IS_WINDOWS = sys.platform == "win32"

# Suppress CMD window pop-ups when running as a --windowed exe (Windows only)
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _run(cmd: list) -> Tuple[int, str, str]:
    """Run a subprocess command and return (returncode, stdout, stderr)."""
    kwargs = dict(capture_output=True, text=True, timeout=15)
    if IS_WINDOWS:
        kwargs["creationflags"] = _NO_WINDOW
    result = subprocess.run(cmd, **kwargs)
    return result.returncode, result.stdout, result.stderr


def _is_connected() -> bool:
    """Check internet connectivity by attempting a TCP connection to Google DNS."""
    try:
        socket.setdefaulttimeout(3)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(
            (CONNECTIVITY_CHECK_HOST, CONNECTIVITY_CHECK_PORT)
        )
        return True
    except (socket.error, OSError):
        return False


def _wait_for_connectivity(timeout: int = CONNECT_TIMEOUT_SECONDS) -> bool:
    """
    Poll until internet connectivity is confirmed or timeout is reached.
    Returns True if connected, False if timeout exceeded.
    """
    logger.info(f"Waiting for internet connectivity (timeout={timeout}s)...")
    start = time.time()
    while time.time() - start < timeout:
        if _is_connected():
            logger.info("Internet connectivity confirmed.")
            return True
        time.sleep(2)
    logger.warning("Timed out waiting for internet connectivity.")
    return False


# ── Public API ─────────────────────────────────────────────────────────────────

def disconnect():
    """Disconnect from the current WiFi network."""
    if IS_WINDOWS:
        _disconnect_windows()
    else:
        _disconnect_linux()


def connect(ssid: str, password: str, max_retries: int = 5) -> bool:
    """
    Connect to a WiFi network by SSID, with multiple retries.
    Returns True if connection was successful.
    """
    logger.info(f"Connecting to SSID: {ssid}")
    if IS_WINDOWS:
        return _connect_windows(ssid, password, max_retries)
    else:
        return _connect_linux(ssid, password, max_retries)


def get_current_ssid() -> str:
    """Return the currently connected WiFi SSID, or empty string if not connected."""
    if IS_WINDOWS:
        return _get_current_ssid_windows()
    else:
        return _get_current_ssid_linux()


# ── Windows implementation ─────────────────────────────────────────────────────

def _disconnect_windows():
    code, out, err = _run(["netsh", "wlan", "disconnect"])
    logger.debug(f"Disconnect result: {code} | {out.strip()}")
    time.sleep(1)


def _connect_windows(ssid: str, password: str, max_retries: int) -> bool:
    profile_xml = _build_wifi_profile_windows(ssid, password)
    profile_path = f"C:\\Temp\\wifi_profile_{ssid.replace(' ', '_')}.xml"

    try:
        os.makedirs("C:\\Temp", exist_ok=True)
        with open(profile_path, "w", encoding="utf-8") as f:
            f.write(profile_xml)

        code, out, err = _run(["netsh", "wlan", "add", "profile",
                                f"filename={profile_path}", "user=current"])
        logger.debug(f"Add profile: {code} | {out.strip()}")

        for attempt in range(1, max_retries + 1):
            if attempt > 1:
                logger.info(f"WiFi connection retry {attempt}/{max_retries} for {ssid}...")
                _disconnect_windows()
                time.sleep(2)

            code, out, err = _run(["netsh", "wlan", "connect",
                                    f"name={ssid}", f"ssid={ssid}"])
            logger.debug(f"Connect attempt {attempt}: {code} | {out.strip()}")

            if code != 0:
                logger.error(f"Failed to issue connect command for {ssid}")
                continue

            if _wait_for_connectivity():
                return True

        logger.error(f"Failed to connect to {ssid} after {max_retries} attempts.")
        return False

    finally:
        try:
            os.remove(profile_path)
        except Exception:
            pass


def _get_current_ssid_windows() -> str:
    try:
        code, out, err = _run(["netsh", "wlan", "show", "interfaces"])
        for line in out.splitlines():
            if "SSID" in line and "BSSID" not in line:
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip()
    except Exception as e:
        logger.error(f"Could not get current SSID: {e}")
    return ""


def _build_wifi_profile_windows(ssid: str, password: str) -> str:
    """Generate a Windows WiFi XML profile for WPA2-Personal networks."""
    if password:
        return f"""<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
  <name>{ssid}</name>
  <SSIDConfig>
    <SSID>
      <name>{ssid}</name>
    </SSID>
  </SSIDConfig>
  <connectionType>ESS</connectionType>
  <connectionMode>auto</connectionMode>
  <MSM>
    <security>
      <authEncryption>
        <authentication>WPA2PSK</authentication>
        <encryption>AES</encryption>
        <useOneX>false</useOneX>
      </authEncryption>
      <sharedKey>
        <keyType>passPhrase</keyType>
        <protected>false</protected>
        <keyMaterial>{password}</keyMaterial>
      </sharedKey>
    </security>
  </MSM>
</WLANProfile>"""
    else:
        return f"""<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
  <name>{ssid}</name>
  <SSIDConfig>
    <SSID>
      <name>{ssid}</name>
    </SSID>
  </SSIDConfig>
  <connectionType>ESS</connectionType>
  <connectionMode>auto</connectionMode>
  <MSM>
    <security>
      <authEncryption>
        <authentication>open</authentication>
        <encryption>none</encryption>
        <useOneX>false</useOneX>
      </authEncryption>
    </security>
  </MSM>
</WLANProfile>"""


# ── Linux implementation (nmcli / NetworkManager) ──────────────────────────────

def _disconnect_linux():
    """Disconnect the active WiFi device using nmcli."""
    # Find the WiFi device name (e.g. wlan0, wlp2s0)
    device = _get_wifi_device_linux()
    if device:
        code, out, err = _run(["nmcli", "device", "disconnect", device])
        logger.debug(f"nmcli disconnect: {code} | {out.strip()}")
    time.sleep(1)


def _connect_linux(ssid: str, password: str, max_retries: int) -> bool:
    """Connect to a WiFi network using nmcli."""
    for attempt in range(1, max_retries + 1):
        if attempt > 1:
            logger.info(f"WiFi connection retry {attempt}/{max_retries} for {ssid}...")
            _disconnect_linux()
            time.sleep(2)

        if password:
            cmd = ["nmcli", "device", "wifi", "connect", ssid,
                   "password", password]
        else:
            cmd = ["nmcli", "device", "wifi", "connect", ssid]

        code, out, err = _run(cmd)
        logger.debug(f"nmcli connect attempt {attempt}: {code} | {out.strip()}")

        if code == 0 and _wait_for_connectivity():
            return True

        logger.warning(f"nmcli connect attempt {attempt} failed: {err.strip() or out.strip()}")

    logger.error(f"Failed to connect to {ssid} after {max_retries} attempts.")
    return False


def _get_current_ssid_linux() -> str:
    """Return current WiFi SSID via nmcli."""
    try:
        code, out, err = _run(
            ["nmcli", "-t", "-f", "active,ssid", "device", "wifi"]
        )
        for line in out.splitlines():
            # Output format: "yes:MySSID"
            if line.startswith("yes:"):
                return line[4:].strip()
    except Exception as e:
        logger.error(f"Could not get current SSID: {e}")
    return ""


def _get_wifi_device_linux() -> str:
    """Return the name of the first WiFi device (e.g. 'wlan0')."""
    try:
        code, out, err = _run(
            ["nmcli", "-t", "-f", "device,type", "device", "status"]
        )
        for line in out.splitlines():
            parts = line.split(":")
            if len(parts) >= 2 and parts[1].strip() == "wifi":
                return parts[0].strip()
    except Exception as e:
        logger.error(f"Could not find WiFi device: {e}")
    return ""
