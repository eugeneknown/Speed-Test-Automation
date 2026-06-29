"""
speed_tester.py
Uses Playwright (headless Chromium) to run a speed test on fast.com
and capture a screenshot of the result.
"""

import logging
import time
from pathlib import Path
from datetime import datetime
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

SCREENSHOTS_DIR = Path(__file__).parent.parent / "screenshots"
FAST_COM_URL = "https://fast.com"

# Selectors on fast.com
SPEED_VALUE_SELECTOR = "#speed-value"
SPEED_UNIT_SELECTOR = "#speed-units"
RESULT_CONTAINER_SELECTOR = "#speed-progress-indicator"
DONE_INDICATOR = ".succeeded"


def run_speed_test(
    url: str = FAST_COM_URL,
    isp_name: str = "unknown"
) -> Tuple[bool, str, Optional[Path]]:
    """
    Launch a headless browser, navigate to fast.com, wait for the speed
    result, then take a screenshot.

    Returns:
        (success: bool, speed_label: str, screenshot_path: Path | None)
        speed_label examples: "95 Mbps", "1.2 Gbps", "NO CONNECTION"
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

            logger.info(f"Navigating to {url} for ISP: {isp_name}")
            page.goto(url, timeout=30000)

            # Wait for speed value element to appear
            page.wait_for_selector(SPEED_VALUE_SELECTOR, timeout=15000)

            # Wait for the test to complete — fast.com adds .succeeded when done
            logger.info("Waiting for speed test to complete...")
            try:
                page.wait_for_selector(DONE_INDICATOR, timeout=90000)
            except PWTimeout:
                logger.warning("Speed test did not reach 'succeeded' state in 90s — capturing current value.")

            # Give it a moment to settle
            time.sleep(2)

            # Extract the speed value and unit
            speed_value = page.locator(SPEED_VALUE_SELECTOR).inner_text(timeout=5000).strip()
            speed_unit = page.locator(SPEED_UNIT_SELECTOR).inner_text(timeout=5000).strip()
            speed_label = f"{speed_value} {speed_unit}".strip()

            if not speed_value or speed_value == "0":
                logger.warning("Speed value is 0 or empty — possible failed test.")

            # Take screenshot
            page.screenshot(path=str(screenshot_path), full_page=False)
            logger.info(f"Screenshot saved: {screenshot_path}")

            browser.close()

        return True, speed_label, screenshot_path

    except PWTimeout:
        logger.error(f"Timeout during speed test for ISP: {isp_name}")
        return False, "TIMEOUT", None
    except Exception as e:
        logger.error(f"Speed test error for {isp_name}: {e}")
        return False, "ERROR", None
