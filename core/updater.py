"""
updater.py
Handles fetching the latest release from GitHub, downloading the new executable,
and orchestrating the file-swap via a batch script to auto-update the application.
"""

import os
import sys
import json
import stat
import urllib.request
import logging
import threading
import subprocess
from typing import Optional, Callable
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0

from core.version import __version__, GITHUB_REPO

logger = logging.getLogger(__name__)

def parse_version(v_str: str) -> tuple:
    """Convert a version string like 'v1.0.2' into a tuple (1, 0, 2) for comparison."""
    clean = v_str.lower().replace('v', '').strip()
    return tuple(map(int, clean.split('.')))


def check_for_updates() -> Optional[dict]:
    """
    Checks the GitHub API for the latest release.
    Returns the release dict if a newer version is found, else None.
    Searches for a .exe asset on Windows, or a Linux binary/tarball otherwise.
    """
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SpeedTestAuto-Updater"})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())

            latest_version_str = data.get("tag_name", "0.0.0")

            if parse_version(latest_version_str) > parse_version(__version__):
                # Find the right asset for this platform
                for asset in data.get("assets", []):
                    name: str = asset.get("name", "")
                    is_match = name.endswith(".exe") if IS_WINDOWS else (
                        "linux" in name.lower() or name.endswith(".tar.gz")
                    )
                    if is_match:
                        return {
                            "version": latest_version_str,
                            "download_url": asset.get("browser_download_url"),
                            "release_notes": data.get("body", "")
                        }
        return None
    except Exception as e:
        logger.error(f"Failed to check for updates: {e}")
        return None


def download_and_install_update(download_url: str, progress_callback: Callable[[int], None] = None):
    """
    Downloads the new executable and triggers the swap script.
    Must be run in a background thread if blocking a GUI.
    """
    # Only allow updates if running as a frozen executable
    if not getattr(sys, 'frozen', False):
        logger.warning("Cannot auto-update when running from python script. Please run from compiled binary.")
        return False

    current_exe = Path(sys.executable)

    if IS_WINDOWS:
        new_exe = current_exe.with_name(current_exe.stem + "_new.exe")
        swap_script = current_exe.with_name("update_swap.bat")
    else:
        new_exe = current_exe.with_name(current_exe.name + ".new")
        swap_script = current_exe.with_name("update_swap.sh")

    try:
        logger.info(f"Downloading update from {download_url}...")

        req = urllib.request.Request(download_url, headers={"User-Agent": "SpeedTestAuto-Updater"})
        with urllib.request.urlopen(req, timeout=30) as response:
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            block_size = 8192

            with open(new_exe, 'wb') as f:
                while True:
                    buffer = response.read(block_size)
                    if not buffer:
                        break
                    f.write(buffer)
                    downloaded += len(buffer)
                    if total_size > 0 and progress_callback:
                        percent = int((downloaded / total_size) * 100)
                        progress_callback(percent)

        logger.info("Download complete. Creating swap script...")

        if IS_WINDOWS:
            script_content = f"""@echo off
echo Updating SpeedTest Automation... Please wait.
timeout /t 3 /nobreak > NUL
del "{current_exe.name}"
ren "{new_exe.name}" "{current_exe.name}"
start "" "{current_exe.name}"
del "%~f0"
"""
            with open(swap_script, "w") as f:
                f.write(script_content)

            logger.info("Executing swap script and exiting...")
            subprocess.Popen(
                [str(swap_script)],
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
        else:
            script_content = f"""#!/bin/bash
echo "Updating SpeedTest Automation... Please wait."
sleep 3
mv "{new_exe}" "{current_exe}"
chmod +x "{current_exe}"
"{current_exe}" &
rm -- "$0"
"""
            with open(swap_script, "w") as f:
                f.write(script_content)
            # Make the shell script executable
            swap_script.chmod(swap_script.stat().st_mode | stat.S_IEXEC)

            logger.info("Executing swap script and exiting...")
            subprocess.Popen(["bash", str(swap_script)])

        # Kill the current application
        os._exit(0)

    except Exception as e:
        logger.error(f"Failed to install update: {e}")
        if new_exe.exists():
            new_exe.unlink()
        return False
