"""
wifi_switcher.py
Controls Windows WiFi connections using netsh wlan commands.
Switches between ISP SSIDs and verifies connectivity before returning.
"""

import subprocess
import time
import socket
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

CONNECT_TIMEOUT_SECONDS = 30
CONNECTIVITY_CHECK_HOST = "8.8.8.8"
CONNECTIVITY_CHECK_PORT = 53


def _run(cmd: list) -> Tuple[int, str, str]:
    """Run a subprocess command and return (returncode, stdout, stderr)."""
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=15
    )
    return result.returncode, result.stdout, result.stderr


def disconnect():
    """Disconnect from the current WiFi network."""
    code, out, err = _run(["netsh", "wlan", "disconnect"])
    logger.debug(f"Disconnect result: {code} | {out.strip()}")
    time.sleep(1)


def connect(ssid: str, password: str, max_retries: int = 5) -> bool:
    """
    Connect to a WiFi network by SSID, with multiple retries.
    Creates a temporary profile if needed, then connects.
    Returns True if connection was successful.
    """
    logger.info(f"Connecting to SSID: {ssid}")

    # Build a temporary XML profile for the SSID
    profile_xml = _build_wifi_profile(ssid, password)
    profile_path = f"C:\\Temp\\wifi_profile_{ssid.replace(' ', '_')}.xml"

    try:
        import os
        os.makedirs("C:\\Temp", exist_ok=True)
        with open(profile_path, "w", encoding="utf-8") as f:
            f.write(profile_xml)

        # Add the profile (only needs to be done once)
        code, out, err = _run(["netsh", "wlan", "add", "profile",
                                f"filename={profile_path}", "user=current"])
        logger.debug(f"Add profile: {code} | {out.strip()}")

        for attempt in range(1, max_retries + 1):
            if attempt > 1:
                logger.info(f"WiFi connection retry {attempt}/{max_retries} for {ssid}...")
                disconnect()
                time.sleep(2)

            # Connect using the profile
            code, out, err = _run(["netsh", "wlan", "connect",
                                    f"name={ssid}", f"ssid={ssid}"])
            logger.debug(f"Connect attempt {attempt}: {code} | {out.strip()}")

            if code != 0:
                logger.error(f"Failed to issue connect command for {ssid}")
                continue

            # Wait for connectivity
            if _wait_for_connectivity():
                return True
                
        logger.error(f"Failed to connect to {ssid} after {max_retries} attempts.")
        return False

    finally:
        try:
            os.remove(profile_path)
        except Exception:
            pass


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


def get_current_ssid() -> str:
    """Return the currently connected WiFi SSID, or empty string if not connected."""
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


def _build_wifi_profile(ssid: str, password: str) -> str:
    """Generate a Windows WiFi XML profile for WPA2-Personal networks."""
    if password:
        auth_block = f"""
        <authentication>WPA2PSK</authentication>
        <encryption>AES</encryption>
      </security>
    </MSM>
    <containerId>{{00000000-0000-0000-0000-000000000000}}</containerId>
  </WLANProfile>"""

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
        # Open network (no password)
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
