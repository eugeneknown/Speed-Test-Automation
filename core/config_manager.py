"""
config_manager.py
Handles loading, saving, and validating ISP configurations and app state.
All data is persisted to JSON files in the /data directory.
"""

import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

def get_base_dir() -> Path:
    """Return the base directory for data and screenshots, handling PyInstaller."""
    if getattr(sys, 'frozen', False):
        return Path.home() / "Documents" / "SpeedTestAutomation"
    return Path(__file__).parent.parent


def extract_bundled_credentials() -> Optional[str]:
    """
    When running as a frozen exe, look for a bundled client_secret*.json inside
    the PyInstaller _MEIPASS bundle.  If found and no credentials path is
    already configured, copy it to the writable base dir and save the path.

    Returns the final path string, or None if not applicable / already set.
    """
    if not getattr(sys, 'frozen', False):
        return None  # Only relevant for the packaged exe

    # Already configured — nothing to do
    current = load_config().get("service_account_path", "")
    if current and Path(current).exists():
        return current

    # Search the bundle for client_secret*.json
    bundle_dir = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    matches = list(bundle_dir.glob("client_secret*.json"))
    if not matches:
        return None

    # Copy to the writable user directory
    dest_dir = get_base_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / matches[0].name

    import shutil
    shutil.copy2(str(matches[0]), str(dest_path))

    # Save path into config so the GUI picks it up automatically
    set_service_account_path(str(dest_path))
    return str(dest_path)


DATA_DIR = get_base_dir() / "data"
CONFIG_FILE = DATA_DIR / "config.json"
STATE_FILE = DATA_DIR / "state.json"

DEFAULT_CONFIG = {
    "service_account_path": "",
    "drive_folder_name": "SpeedTest Results",
    "run_on_startup": False,
    "auto_start_scheduler": False,
    "isps": []
}

DEFAULT_ISP = {
    "id": "",
    "name": "",
    "ssid": "",
    "password": "",
    "spreadsheet_name": "",
    "speed_test_url": "https://fast.com",
    "interval_hours": 2,
    "active_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
    "enabled": True
}

DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
INTERVAL_OPTIONS = [1, 2, 3, 4, 6, 12]


def ensure_data_dir():
    """Create the data directory if it doesn't exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> Dict[str, Any]:
    """Load the full app configuration from disk."""
    ensure_data_dir()
    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config: Dict[str, Any]):
    """Save the full app configuration to disk."""
    ensure_data_dir()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def get_isps() -> List[Dict[str, Any]]:
    """Return the list of ISP configurations."""
    return load_config().get("isps", [])


def get_isp_by_id(isp_id: str) -> Optional[Dict[str, Any]]:
    """Return a single ISP config by ID."""
    for isp in get_isps():
        if isp.get("id") == isp_id:
            return isp
    return None


def save_isp(isp: Dict[str, Any]):
    """Add or update an ISP config (matched by id)."""
    config = load_config()
    isps = config.get("isps", [])
    for i, existing in enumerate(isps):
        if existing.get("id") == isp.get("id"):
            isps[i] = isp
            config["isps"] = isps
            save_config(config)
            return
    isps.append(isp)
    config["isps"] = isps
    save_config(config)


def delete_isp(isp_id: str):
    """Remove an ISP config by ID."""
    config = load_config()
    config["isps"] = [i for i in config.get("isps", []) if i.get("id") != isp_id]
    save_config(config)


def get_service_account_path() -> str:
    """Return the path to the Google Service Account credentials JSON."""
    return load_config().get("service_account_path", "")


def set_service_account_path(path: str):
    """Update the service account credentials path."""
    config = load_config()
    config["service_account_path"] = path
    save_config(config)


def get_drive_folder_name() -> str:
    """Return the Google Drive root folder name for screenshots."""
    return load_config().get("drive_folder_name", "SpeedTest Results")


# ─── State Management ────────────────────────────────────────────────────────

def load_state() -> Dict[str, Any]:
    """Load the runtime state (last run timestamps per ISP)."""
    ensure_data_dir()
    if not STATE_FILE.exists():
        return {}
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state: Dict[str, Any]):
    """Persist runtime state to disk."""
    ensure_data_dir()
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def get_last_run(isp_id: str) -> Optional[str]:
    """Return the ISO timestamp of the last run for a given ISP."""
    return load_state().get(isp_id, {}).get("last_run")


def set_last_run(isp_id: str, timestamp: str):
    """Record the last run timestamp for a given ISP."""
    state = load_state()
    if isp_id not in state:
        state[isp_id] = {}
    state[isp_id]["last_run"] = timestamp
    save_state(state)


def new_isp_template() -> Dict[str, Any]:
    """Return a fresh ISP config dict with a unique ID."""
    import uuid
    isp = DEFAULT_ISP.copy()
    isp["id"] = str(uuid.uuid4())
    isp["active_days"] = list(DEFAULT_ISP["active_days"])
    return isp
