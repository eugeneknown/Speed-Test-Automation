"""
speed_tester.py
Uses Playwright (headless Chromium) to run a speed test on fast.com
and capture a screenshot of the result, including latency from
the "Show more info" panel.
"""

import logging
import time
from pathlib import Path
from datetime import datetime
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

from core.config_manager import get_base_dir
SCREENSHOTS_DIR = get_base_dir() / "screenshots"
FAST_COM_URL = "https://fast.com"

# Selectors on fast.com
SPEED_VALUE_SELECTOR = "#speed-value"
SPEED_UNIT_SELECTOR = "#speed-units"
RESULT_CONTAINER_SELECTOR = "#speed-progress-indicator"
DONE_INDICATOR = ".succeeded"
SHOW_MORE_BUTTON_SELECTOR = "#show-more-details-link"
LATENCY_UNLOADED_SELECTOR = "#latency-value"
LATENCY_LOADED_SELECTOR = "#bufferbloat-value"


def run_speed_test(
    url: str = FAST_COM_URL,
    isp_name: str = "unknown"
) -> Tuple[bool, str, Optional[Path], Optional[str], Optional[str]]:
    """
    Launch a headless browser, navigate to fast.com, wait for the speed
    result, click "Show more info" to reveal latency values, then take
    a screenshot.

    Returns:
        (success, speed_label, screenshot_path, latency_unloaded, latency_loaded)
        speed_label examples: "95 Mbps", "1.2 Gbps", "NO CONNECTION"
        latency values: e.g. "2 ms", "13 ms", or None if unavailable
    """
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_filename = f"{isp_name.replace(' ', '_')}_{timestamp_str}.png"
    screenshot_path = SCREENSHOTS_DIR / screenshot_filename

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

            # Navigate with retries — ERR_NETWORK_CHANGED can fire in the brief
            # window while WiFi finishes stabilising after a switch.
            GOTO_RETRIES = 3
            GOTO_RETRY_WAIT = 8  # seconds between retries
            for nav_attempt in range(1, GOTO_RETRIES + 1):
                try:
                    logger.info(
                        f"Navigating to {url} for ISP: {isp_name}"
                        + (f" (attempt {nav_attempt})" if nav_attempt > 1 else "")
                    )
                    page.goto(url, timeout=30000)
                    break  # success
                except Exception as nav_err:
                    err_str = str(nav_err)
                    transient = any(k in err_str for k in (
                        "ERR_NETWORK_CHANGED",
                        "ERR_INTERNET_DISCONNECTED",
                        "ERR_NAME_NOT_RESOLVED",
                        "ERR_CONNECTION_RESET",
                        "net::",
                    ))
                    if transient and nav_attempt < GOTO_RETRIES:
                        logger.warning(
                            f"Navigation failed ({err_str.splitlines()[0]}) — "
                            f"retrying in {GOTO_RETRY_WAIT}s..."
                        )
                        time.sleep(GOTO_RETRY_WAIT)
                        page.close()
                        page = context.new_page()
                    else:
                        raise  # non-transient or out of retries

            # Wait for speed value element to appear
            page.wait_for_selector(SPEED_VALUE_SELECTOR, timeout=15000)

            # Phase 1 — wait for download to finish (.succeeded appears after download)
            logger.info("Waiting for download phase to complete...")
            try:
                page.wait_for_selector(DONE_INDICATOR, timeout=90000)
            except PWTimeout:
                logger.warning("Speed test did not reach 'succeeded' state in 90s — capturing current value.")

            # Phase 2 — wait for upload to finish (upload-value becomes non-zero)
            logger.info("Waiting for upload phase to complete...")
            UPLOAD_VALUE_SELECTOR = "#upload-value"
            upload_wait_s = 60
            upload_poll_interval = 1
            for _ in range(upload_wait_s // upload_poll_interval):
                try:
                    upload_val = page.locator(UPLOAD_VALUE_SELECTOR).inner_text(timeout=2000).strip()
                    if upload_val and upload_val not in ("0", ""):
                        logger.info(f"Upload phase complete: {upload_val}")
                        break
                except Exception:
                    pass
                time.sleep(upload_poll_interval)
            else:
                logger.warning("Upload value stayed at 0 after 60s — capturing current state.")

            # Brief settle time
            time.sleep(1)

            # Extract the speed value and unit
            speed_value = page.locator(SPEED_VALUE_SELECTOR).inner_text(timeout=5000).strip()
            speed_unit = page.locator(SPEED_UNIT_SELECTOR).inner_text(timeout=5000).strip()
            speed_label = f"{speed_value} {speed_unit}".strip()

            if not speed_value or speed_value == "0":
                logger.warning("Speed value is 0 or empty — possible failed test.")

            # ── Reveal and extract latency values ─────────────────────────
            latency_unloaded: Optional[str] = None
            latency_loaded: Optional[str] = None
            try:
                show_more = page.locator(SHOW_MORE_BUTTON_SELECTOR)
                if show_more.is_visible(timeout=5000):
                    show_more.click()
                    logger.info("Clicked 'Show more info' — waiting for latency values...")
                    # Wait for the unloaded latency element to become visible
                    page.wait_for_selector(LATENCY_UNLOADED_SELECTOR, timeout=15000)
                    time.sleep(1)  # let the loaded value populate too

                    unloaded_val = page.locator(LATENCY_UNLOADED_SELECTOR).inner_text(timeout=5000).strip()
                    loaded_val = page.locator(LATENCY_LOADED_SELECTOR).inner_text(timeout=5000).strip()

                    # fast.com shows the unit separately; fetch them too
                    unloaded_unit_els = page.locator("#latency-units").all()
                    loaded_unit_els = page.locator("#bufferbloat-units").all()

                    unloaded_unit = unloaded_unit_els[0].inner_text(timeout=3000).strip() if unloaded_unit_els else "ms"
                    loaded_unit = loaded_unit_els[0].inner_text(timeout=3000).strip() if loaded_unit_els else "ms"

                    latency_unloaded = f"{unloaded_val} {unloaded_unit}".strip() if unloaded_val else None
                    latency_loaded = f"{loaded_val} {loaded_unit}".strip() if loaded_val else None
                    logger.info(f"Latency — Unloaded: {latency_unloaded}, Loaded: {latency_loaded}")
                else:
                    logger.warning("'Show more info' button not visible — latency not captured.")
            except Exception as lat_err:
                logger.warning(f"Could not extract latency values: {lat_err}")

            # Take screenshot (now includes the expanded latency panel)
            page.screenshot(path=str(screenshot_path), full_page=False)
            logger.info(f"Screenshot saved: {screenshot_path}")

            browser.close()

        return True, speed_label, screenshot_path, latency_unloaded, latency_loaded

    except PWTimeout:
        logger.error(f"Timeout during speed test for ISP: {isp_name}")
        return False, "TIMEOUT", None, None, None
    except Exception as e:
        logger.error(f"Speed test error for {isp_name}: {e}")
        return False, "ERROR", None, None, None
