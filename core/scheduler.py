"""
scheduler.py
Manages per-ISP scheduled speed test jobs using APScheduler.
Each ISP runs independently based on its configured interval and active days.
The full pipeline per ISP: WiFi switch → speed test → Drive upload → Sheets log.
"""

import logging
import threading
from datetime import datetime, timedelta
from typing import Callable, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from core import config_manager, wifi_switcher, speed_tester, drive_uploader, sheets_logger

logger = logging.getLogger(__name__)

# Callback type for GUI log updates: fn(isp_name, message, level)
LogCallback = Callable[[str, str, str], None]

_scheduler: Optional[BackgroundScheduler] = None
_lock = threading.Lock()
_log_callback: Optional[LogCallback] = None


def set_log_callback(fn: LogCallback):
    """Register a callback to receive log messages (for GUI display)."""
    global _log_callback
    _log_callback = fn


def _emit(isp_name: str, message: str, level: str = "info"):
    """Send a log message to the logger and the GUI callback."""
    getattr(logger, level)(f"[{isp_name}] {message}")
    if _log_callback:
        try:
            _log_callback(isp_name, message, level)
        except Exception:
            pass


def run_isp_cycle(isp: dict):
    """
    Execute the full recording cycle for one ISP:
    1. Check if today is an active day
    2. Check if enough time has passed since last run
    3. Switch WiFi
    4. Run speed test
    5. Upload screenshot to Drive
    6. Log to Google Sheets
    """
    with _lock:
        isp_id = isp["id"]
        isp_name = isp["name"]
        today = datetime.now().strftime("%A")

        # Check active day
        if today not in isp.get("active_days", []):
            _emit(isp_name, f"Skipping — '{today}' is not an active day.", "debug")
            return

        # Check interval (recover from restarts)
        last_run_str = config_manager.get_last_run(isp_id)
        interval_hours = isp.get("interval_hours", 2)
        if last_run_str:
            last_run = datetime.fromisoformat(last_run_str)
            due_at = last_run + timedelta(hours=interval_hours)
            if datetime.now() < due_at:
                _emit(isp_name, f"Skipping — next run due at {due_at.strftime('%I:%M %p')}.", "debug")
                return

        _emit(isp_name, f"Starting speed test cycle...")

        # ── Step 1: Switch WiFi ────────────────────────────────────────────
        _emit(isp_name, f"Switching WiFi to '{isp['ssid']}'...")
        wifi_switcher.disconnect()
        connected = wifi_switcher.connect(isp["ssid"], isp.get("password", ""))

        if not connected:
            _emit(isp_name, "No internet connection — logging NO CONNECTION.", "warning")
            _log_no_connection(isp)
            config_manager.set_last_run(isp_id, datetime.now().isoformat())
            return

        _emit(isp_name, "WiFi connected successfully.")

        # ── Step 2: Speed Test ─────────────────────────────────────────────
        _emit(isp_name, "Running speed test on fast.com...")
        url = isp.get("speed_test_url", "https://fast.com")
        success, speed_label, screenshot_path = speed_tester.run_speed_test(url, isp_name)

        if not success:
            _emit(isp_name, f"Speed test failed ({speed_label}) — logging failure.", "warning")
            _log_no_connection(isp, label=speed_label)
            config_manager.set_last_run(isp_id, datetime.now().isoformat())
            return

        _emit(isp_name, f"Speed result: {speed_label}")

        # ── Step 3: Upload Screenshot ──────────────────────────────────────
        credentials_path = config_manager.get_service_account_path()
        drive_folder = config_manager.get_drive_folder_name()
        image_url = None

        if screenshot_path and credentials_path:
            _emit(isp_name, "Uploading screenshot to Google Drive...")
            upload_ok, image_url = drive_uploader.upload_screenshot(
                credentials_path, screenshot_path, isp_name, drive_folder
            )
            if upload_ok:
                _emit(isp_name, "Screenshot uploaded successfully.")
            else:
                _emit(isp_name, "Screenshot upload failed — will log without image.", "warning")
        else:
            _emit(isp_name, "Skipping screenshot upload (no credentials or no file).", "warning")

        # ── Step 4: Log to Sheets ──────────────────────────────────────────
        if credentials_path:
            _emit(isp_name, f"Logging to Google Sheets: '{isp['spreadsheet_name']}'...")
            logged = sheets_logger.log_result(
                credentials_path,
                isp["spreadsheet_name"],
                speed_label,
                image_url
            )
            if logged:
                _emit(isp_name, "✅ Result logged successfully.")
            else:
                _emit(isp_name, "❌ Failed to log to Google Sheets.", "error")
        else:
            _emit(isp_name, "No service account configured — skipping Sheets logging.", "warning")

        config_manager.set_last_run(isp_id, datetime.now().isoformat())


def _log_no_connection(isp: dict, label: str = "NO CONNECTION"):
    """Log a no-connection row to Google Sheets."""
    credentials_path = config_manager.get_service_account_path()
    if credentials_path:
        sheets_logger.log_result(
            credentials_path,
            isp["spreadsheet_name"],
            label,
            image_url=None
        )


def start():
    """Start the background scheduler with jobs for all enabled ISPs."""
    global _scheduler

    if _scheduler and _scheduler.running:
        logger.info("Scheduler already running.")
        return

    _scheduler = BackgroundScheduler(daemon=True)

    isps = config_manager.get_isps()
    enabled = [i for i in isps if i.get("enabled", True)]

    if not enabled:
        logger.warning("No enabled ISPs found — scheduler started with no jobs.")
    
    for isp in enabled:
        interval_hours = isp.get("interval_hours", 2)
        _scheduler.add_job(
            func=run_isp_cycle,
            trigger=IntervalTrigger(minutes=1),  # Check every minute; cycle decides if it's time
            id=isp["id"],
            name=isp["name"],
            args=[isp],
            replace_existing=True,
            max_instances=1
        )
        logger.info(
            f"Scheduled ISP '{isp['name']}' — "
            f"every {interval_hours}h on {', '.join(isp.get('active_days', []))}"
        )

    _scheduler.start()
    logger.info("Scheduler started.")


def stop():
    """Stop the background scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")


def restart():
    """Restart the scheduler (call after config changes)."""
    stop()
    start()


def is_running() -> bool:
    """Return True if the scheduler is active."""
    return _scheduler is not None and _scheduler.running


def run_now(isp_id: str):
    """Manually trigger an immediate cycle for a specific ISP (bypasses interval check)."""
    isp = config_manager.get_isp_by_id(isp_id)
    if not isp:
        logger.error(f"ISP not found: {isp_id}")
        return
    # Clear last run so the interval check passes
    config_manager.set_last_run(isp_id, "")
    thread = threading.Thread(target=run_isp_cycle, args=[isp], daemon=True)
    thread.start()
