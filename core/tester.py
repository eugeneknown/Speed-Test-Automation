"""
tester.py
End-to-end configuration test runner.
Each test function returns (success: bool, detail: str).
Designed to be called from the GUI test dialog in a background thread.
"""

import logging
from pathlib import Path
from typing import Callable, Tuple

logger = logging.getLogger(__name__)

# Type alias for the step callback:  fn(step_index, success, detail)
StepCallback = Callable[[int, bool, str], None]


# ── Individual test steps ──────────────────────────────────────────────────────

def test_credentials_file(credentials_path: str) -> Tuple[bool, str]:
    """Step 1 — Verify the credentials JSON file is valid and readable."""
    import json
    from pathlib import Path

    path = Path(credentials_path)
    if not path.exists():
        return False, f"File not found: {credentials_path}"
    if path.suffix.lower() != ".json":
        return False, "File must be a .json file."
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "installed" not in data and "web" not in data:
            return False, "Invalid JSON: missing 'installed' or 'web'. Ensure it is an OAuth Desktop Client JSON."
        return True, "Valid OAuth Client ID file."
    except Exception as e:
        return False, str(e)


def test_google_auth(credentials_path: str) -> Tuple[bool, str]:
    """Step 2 — Build a Google auth token (validates key pair works)."""
    try:
        from core import auth
        creds = auth.get_credentials(credentials_path)
        if creds and creds.valid:
            return True, "Authentication token obtained successfully."
        return False, "Auth failed: Invalid credentials."
    except Exception as e:
        return False, f"Auth failed: {e}"


def test_drive_access(credentials_path: str, folder_name: str = "SpeedTest Results") -> Tuple[bool, str]:
    """Step 3 — Connect to Google Drive and create/verify a test folder."""
    try:
        from core import auth
        from googleapiclient.discovery import build

        creds = auth.get_credentials(credentials_path)
        service = build("drive", "v3", credentials=creds)

        # List files to confirm Drive access
        result = service.files().list(
            q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
            spaces="drive",
            fields="files(id, name)"
        ).execute()
        files = result.get("files", [])

        if files:
            return True, f"Drive accessible — folder '{folder_name}' found (id={files[0]['id']})."
        else:
            # Create it
            folder = service.files().create(
                body={"name": folder_name, "mimeType": "application/vnd.google-apps.folder"},
                fields="id"
            ).execute()
            return True, f"Drive accessible — created folder '{folder_name}' (id={folder['id']})."
    except Exception as e:
        return False, f"Drive access failed: {e}"


def test_sheets_access(
    credentials_path: str,
    spreadsheet_name: str = "SpeedTest Config Test"
) -> Tuple[bool, str]:
    """Step 4 — Create or find a test Google Spreadsheet."""
    try:
        from core import auth
        from googleapiclient.discovery import build

        creds = auth.get_credentials(credentials_path)
        drive_service = build("drive", "v3", credentials=creds)
        sheets_service = build("sheets", "v4", credentials=creds)

        # Check if the spreadsheet already exists
        q = (
            f"name='{spreadsheet_name}' and "
            f"mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
        )
        result = drive_service.files().list(q=q, spaces="drive", fields="files(id,name)").execute()
        files = result.get("files", [])

        if files:
            sid = files[0]["id"]
            return True, f"Sheets accessible — found existing spreadsheet (id={sid})."

        # Create a new one
        body = {
            "properties": {"title": spreadsheet_name},
            "sheets": [{"properties": {"title": "Config Test"}}]
        }
        ss = sheets_service.spreadsheets().create(body=body, fields="spreadsheetId").execute()
        sid = ss["spreadsheetId"]

        # Write a test row
        sheets_service.spreadsheets().values().update(
            spreadsheetId=sid,
            range="Config Test!A1",
            valueInputOption="USER_ENTERED",
            body={"values": [["Config Test", "✅ Google Sheets connection verified!"]]}
        ).execute()

        return True, f"Sheets accessible — created test spreadsheet (id={sid})."
    except Exception as e:
        return False, f"Sheets access failed: {e}"


def test_screenshot(save_dir: Path = None) -> Tuple[bool, str]:
    """Step 5 — Launch headless Chromium, run fast.com, capture a screenshot."""
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    from datetime import datetime

    if save_dir is None:
        save_dir = Path(__file__).parent.parent / "screenshots"
    save_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = save_dir / f"config_test_{timestamp}.png"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            context = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            )
            page = context.new_page()
            page.goto("https://fast.com", timeout=30000)

            # Wait for speed value element
            page.wait_for_selector("#speed-value", timeout=15000)

            # Wait up to 60s for result to stabilise
            try:
                page.wait_for_selector(".succeeded", timeout=60000)
            except PWTimeout:
                pass  # Capture whatever is shown

            import time
            time.sleep(1)

            speed_val = page.locator("#speed-value").inner_text(timeout=5000).strip()
            speed_unit = page.locator("#speed-units").inner_text(timeout=5000).strip()
            speed_label = f"{speed_val} {speed_unit}".strip()

            page.screenshot(path=str(out_path))
            browser.close()

        return True, f"Screenshot saved — Speed: {speed_label} → {out_path.name}"
    except PWTimeout:
        return False, "Timed out navigating to fast.com — check internet connection."
    except Exception as e:
        return False, f"Screenshot failed: {e}"


def test_drive_upload(
    credentials_path: str,
    screenshot_path: Path,
    folder_name: str = "SpeedTest Results"
) -> Tuple[bool, str]:
    """Step 6 — Upload the test screenshot to Google Drive."""
    try:
        from core.drive_uploader import upload_screenshot
        ok, url = upload_screenshot(
            credentials_path, screenshot_path, "Config Test", folder_name
        )
        if ok:
            return True, f"Upload OK — image URL ready for =IMAGE() formula."
        return False, "Upload returned no URL."
    except Exception as e:
        return False, f"Upload failed: {e}"


# ── Orchestrator ───────────────────────────────────────────────────────────────

STEPS = [
    "Validate credentials file",
    "Authenticate with Google",
    "Access Google Drive",
    "Access Google Sheets",
    "Run fast.com speed test & screenshot",
    "Upload screenshot to Drive",
]


def run_all_tests(
    credentials_path: str,
    drive_folder: str,
    spreadsheet_name: str,
    on_step: StepCallback,
    screenshots_dir: Path = None,
):
    """
    Run all 6 test steps in sequence.
    Calls on_step(index, success, detail) after each step completes.
    Stops early if a critical step fails.
    """
    screenshot_path = None

    # Step 0 — Validate credentials file
    ok, detail = test_credentials_file(credentials_path)
    on_step(0, ok, detail)
    if not ok:
        for i in range(1, len(STEPS)):
            on_step(i, False, "Skipped — credentials invalid.")
        return

    # Step 1 — Google Auth
    ok, detail = test_google_auth(credentials_path)
    on_step(1, ok, detail)
    if not ok:
        for i in range(2, len(STEPS)):
            on_step(i, False, "Skipped — auth failed.")
        return

    # Step 2 — Drive access
    ok, detail = test_drive_access(credentials_path, drive_folder)
    on_step(2, ok, detail)

    # Step 3 — Sheets access
    ok, detail = test_sheets_access(credentials_path, spreadsheet_name)
    on_step(3, ok, detail)

    # Step 4 — Screenshot
    ok, detail = test_screenshot(screenshots_dir)
    on_step(4, ok, detail)
    if ok and screenshots_dir:
        # Find the most recently saved screenshot
        pngs = sorted(screenshots_dir.glob("config_test_*.png"))
        if pngs:
            screenshot_path = pngs[-1]
    elif ok:
        from pathlib import Path as _P
        default_dir = _P(__file__).parent.parent / "screenshots"
        pngs = sorted(default_dir.glob("config_test_*.png"))
        if pngs:
            screenshot_path = pngs[-1]

    # Step 5 — Upload screenshot
    if screenshot_path and screenshot_path.exists():
        ok, detail = test_drive_upload(credentials_path, screenshot_path, drive_folder)
        on_step(5, ok, detail)
    else:
        on_step(5, False, "Skipped — no screenshot to upload.")
