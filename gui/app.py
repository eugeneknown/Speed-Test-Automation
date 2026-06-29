"""
app.py
Main CustomTkinter application window.
Sidebar navigation → Dashboard, ISPs, Logs, Settings.
"""

import customtkinter as ctk
from gui.dashboard import DashboardFrame
from gui.isp_config import ISPConfigFrame
from gui.logs_view import LogsFrame
from gui.settings import SettingsFrame

# ── Theme ─────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ── Palette ────────────────────────────────────────────────────────────────────
BG_DARK      = "#0f1117"
BG_SIDEBAR   = "#161b27"
BG_CARD      = "#1c2333"
ACCENT       = "#4f8ef7"
ACCENT_HOVER = "#3a72d4"
TEXT_PRIMARY  = "#e8eaf6"
TEXT_MUTED    = "#7b8db0"
SUCCESS      = "#4caf7d"
WARNING      = "#f5a623"
DANGER       = "#e05c5c"

NAV_ITEMS = [
    ("📊  Dashboard",  "dashboard"),
    ("📡  ISP Config",  "isps"),
    ("📋  Logs",        "logs"),
    ("⚙️   Settings",   "settings"),
]


class SpeedTestApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("ISP Speed Test Automation")
        self.geometry("1100x700")
        self.minsize(900, 600)
        self.configure(fg_color=BG_DARK)

        self._active_nav = None
        self._frames: dict = {}

        self._build_layout()
        self._navigate("dashboard")

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_layout(self):
        """Build the sidebar + content area layout."""
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar = ctk.CTkFrame(
            self, width=220, corner_radius=0, fg_color=BG_SIDEBAR
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        # Sidebar logo / title
        logo_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        logo_frame.pack(fill="x", padx=20, pady=(24, 16))

        ctk.CTkLabel(
            logo_frame,
            text="⚡ SpeedTrack",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=ACCENT
        ).pack(anchor="w")

        ctk.CTkLabel(
            logo_frame,
            text="ISP Automation",
            font=ctk.CTkFont(size=11),
            text_color=TEXT_MUTED
        ).pack(anchor="w")

        ctk.CTkFrame(self.sidebar, height=1, fg_color="#2a3250").pack(
            fill="x", padx=16, pady=(0, 12)
        )

        # Nav buttons
        self._nav_buttons = {}
        for label, key in NAV_ITEMS:
            btn = ctk.CTkButton(
                self.sidebar,
                text=label,
                anchor="w",
                fg_color="transparent",
                text_color=TEXT_MUTED,
                hover_color="#1e2740",
                font=ctk.CTkFont(size=13),
                height=42,
                corner_radius=8,
                command=lambda k=key: self._navigate(k)
            )
            btn.pack(fill="x", padx=12, pady=2)
            self._nav_buttons[key] = btn

        # Sidebar footer
        ctk.CTkLabel(
            self.sidebar,
            text="v1.0.0",
            font=ctk.CTkFont(size=10),
            text_color=TEXT_MUTED
        ).pack(side="bottom", pady=12)

        # Content area
        self.content = ctk.CTkFrame(self, corner_radius=0, fg_color=BG_DARK)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        # Instantiate all frames
        self._frames["dashboard"] = DashboardFrame(self.content)
        self._frames["isps"] = ISPConfigFrame(self.content)
        self._frames["logs"] = LogsFrame(self.content)
        self._frames["settings"] = SettingsFrame(self.content)

        for frame in self._frames.values():
            frame.grid(row=0, column=0, sticky="nsew")

    # ── Navigation ────────────────────────────────────────────────────────────

    def _navigate(self, key: str):
        """Switch the visible content frame and highlight the active nav button."""
        if self._active_nav:
            self._nav_buttons[self._active_nav].configure(
                fg_color="transparent", text_color=TEXT_MUTED
            )

        self._active_nav = key
        self._nav_buttons[key].configure(
            fg_color=ACCENT, text_color="#ffffff"
        )
        self._frames[key].tkraise()

        # Notify frame it became visible
        if hasattr(self._frames[key], "on_show"):
            self._frames[key].on_show()

    def get_logs_frame(self) -> "LogsFrame":
        return self._frames["logs"]
