"""
config_manager.py
Handles loading, saving, and validating ISP configurations and app state.
All data is persisted to JSON files in the /data directory.
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

DATA_DIR = Path(__file__).parent.parent / "data"
CONFIG_FILE = DATA_DIR / "config.json"
STATE_FILE = DATA_DIR / "state.json"

DEFAULT_CONFIG = {
    "service_account_path": "",
    "drive_folder_name": "SpeedTest Results",
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
