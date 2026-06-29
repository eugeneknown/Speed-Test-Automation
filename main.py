"""
main.py
Entry point for the ISP Speed Test Automation app.
Initialises logging, starts the GUI, wires the scheduler log callback
to the in-app log viewer, and sets up the system tray icon.
"""

import sys
import logging
import threading
import tkinter as tk
from pathlib import Path

# ── Logging setup ──────────────────────────────────────────────────────────────
LOG_FILE = Path(__file__).parent / "data" / "app.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)

# ── Imports ────────────────────────────────────────────────────────────────────
from gui.app import SpeedTestApp
from core import scheduler


def _setup_tray(app: SpeedTestApp):
    """Create a system tray icon so the app can be minimised and restored."""
    try:
        import pystray
        from PIL import Image, ImageDraw

        # Generate a simple icon dynamically (blue circle with ⚡)
        img = Image.new("RGB", (64, 64), color=(15, 17, 23))
        draw = ImageDraw.Draw(img)
        draw.ellipse([4, 4, 60, 60], fill=(79, 142, 247))
        draw.text((20, 18), "⚡", fill=(255, 255, 255))

        def show_window(icon, item):
            icon.stop()
            app.after(0, app.deiconify)

        def quit_app(icon, item):
            icon.stop()
            scheduler.stop()
            app.after(0, app.quit)

        menu = pystray.Menu(
            pystray.MenuItem("Open SpeedTrack", show_window, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", quit_app),
        )
        icon = pystray.Icon("SpeedTrack", img, "SpeedTrack", menu)

        def on_minimize(event):
            if app.state() == "iconic":
                app.withdraw()
                threading.Thread(target=icon.run, daemon=True).start()

        app.bind("<Unmap>", on_minimize)
        logger.info("System tray icon ready.")

    except ImportError:
        logger.warning("pystray or Pillow not available — system tray disabled.")


def main():
    logger.info("Starting ISP Speed Test Automation...")

    app = SpeedTestApp()

    # Wire scheduler log callback → in-app log viewer
    logs_frame = app.get_logs_frame()
    scheduler.set_log_callback(
        lambda isp_name, msg, level: logs_frame.append_log(isp_name, msg, level)
    )

    # System tray
    _setup_tray(app)

    # Handle clean exit
    def on_close():
        logger.info("Shutting down...")
        scheduler.stop()
        app.destroy()

    app.protocol("WM_DELETE_WINDOW", on_close)

    logger.info("GUI started.")
    app.mainloop()


if __name__ == "__main__":
    main()
