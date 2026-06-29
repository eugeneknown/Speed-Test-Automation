"""
logs_view.py
Scrollable in-app activity log panel.
Receives log entries via append_log() called from the scheduler callback.
"""

import customtkinter as ctk
from datetime import datetime

BG_DARK  = "#0f1117"
BG_CARD  = "#1c2333"
ACCENT   = "#4f8ef7"
TEXT_PRIMARY = "#e8eaf6"
TEXT_MUTED   = "#7b8db0"
SUCCESS  = "#4caf7d"
WARNING  = "#f5a623"
DANGER   = "#e05c5c"
BORDER   = "#2a3250"

LEVEL_COLORS = {
    "info":    TEXT_PRIMARY,
    "warning": WARNING,
    "error":   DANGER,
    "debug":   TEXT_MUTED,
    "success": SUCCESS,
}

MAX_LOG_ENTRIES = 300


class LogsFrame(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=BG_DARK, **kwargs)
        self._entries = []
        self._build()

    def _build(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 0))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text="Activity Logs",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=TEXT_PRIMARY
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            header, text="Real-time log of all speed test activity",
            font=ctk.CTkFont(size=12), text_color=TEXT_MUTED
        ).grid(row=1, column=0, sticky="w")

        ctk.CTkButton(
            header, text="🗑  Clear Logs",
            fg_color=BG_CARD, hover_color="#2a3250",
            text_color=TEXT_MUTED, width=120, height=34,
            font=ctk.CTkFont(size=12),
            command=self._clear
        ).grid(row=0, column=1, rowspan=2, sticky="e")

        ctk.CTkFrame(self, height=1, fg_color=BORDER).grid(
            row=0, column=0, sticky="ew", padx=24, pady=(62, 0)
        )

        # Log area
        self.log_box = ctk.CTkTextbox(
            self,
            fg_color=BG_CARD,
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Consolas", size=12),
            wrap="word",
            corner_radius=8,
            border_width=1,
            border_color=BORDER,
            state="disabled"
        )
        self.log_box.grid(row=1, column=0, sticky="nsew", padx=16, pady=12)

        # Tag colors
        self.log_box.tag_config("info",    foreground=TEXT_PRIMARY)
        self.log_box.tag_config("warning", foreground=WARNING)
        self.log_box.tag_config("error",   foreground=DANGER)
        self.log_box.tag_config("debug",   foreground=TEXT_MUTED)
        self.log_box.tag_config("success", foreground=SUCCESS)
        self.log_box.tag_config("ts",      foreground="#3d5a8a")
        self.log_box.tag_config("isp",     foreground=ACCENT)

        self.append_log("System", "Log viewer ready.", "info")

    def append_log(self, isp_name: str, message: str, level: str = "info"):
        """
        Thread-safe log entry append. Called from scheduler thread.
        """
        self.after(0, self._write_log, isp_name, message, level)

    def _write_log(self, isp_name: str, message: str, level: str):
        ts = datetime.now().strftime("%m/%d %I:%M:%S %p")
        self.log_box.configure(state="normal")

        self.log_box.insert("end", f"[{ts}]", "ts")
        self.log_box.insert("end", f" [{isp_name}]", "isp")
        self.log_box.insert("end", f"  {message}\n", level)

        # Trim old entries if too long
        self._entries.append((isp_name, message, level))
        if len(self._entries) > MAX_LOG_ENTRIES:
            self._entries = self._entries[-MAX_LOG_ENTRIES:]
            self.log_box.delete("1.0", f"{MAX_LOG_ENTRIES // 2}.0")

        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _clear(self):
        self._entries.clear()
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")
        self.append_log("System", "Logs cleared.", "debug")

    def on_show(self):
        self.log_box.see("end")
