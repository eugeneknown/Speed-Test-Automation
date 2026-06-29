"""
dashboard.py
Dashboard screen showing ISP status cards with last speed, next run time,
and a Start / Stop scheduler control.
"""

import customtkinter as ctk
from datetime import datetime, timedelta
from typing import Dict

from core import config_manager, scheduler

BG_DARK  = "#0f1117"
BG_CARD  = "#1c2333"
BG_CARD2 = "#202840"
ACCENT   = "#4f8ef7"
TEXT_PRIMARY = "#e8eaf6"
TEXT_MUTED   = "#7b8db0"
SUCCESS  = "#4caf7d"
WARNING  = "#f5a623"
DANGER   = "#e05c5c"
BORDER   = "#2a3250"


class ISPCard(ctk.CTkFrame):
    """A card widget displaying the status of one ISP."""

    def __init__(self, master, isp: dict, **kwargs):
        super().__init__(master, fg_color=BG_CARD, corner_radius=12, **kwargs)
        self.isp = isp
        self._build()

    def _build(self):
        self.configure(border_width=1, border_color=BORDER)
        pad = {"padx": 18, "pady": 6}

        # ISP name header
        header = ctk.CTkFrame(self, fg_color=BG_CARD2, corner_radius=8)
        header.pack(fill="x", padx=12, pady=(12, 4))

        ctk.CTkLabel(
            header,
            text=f"📡  {self.isp['name']}",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=ACCENT
        ).pack(side="left", padx=12, pady=8)

        # Status dot
        self.status_dot = ctk.CTkLabel(
            header, text="●", font=ctk.CTkFont(size=14),
            text_color=TEXT_MUTED
        )
        self.status_dot.pack(side="right", padx=12)

        # Info rows
        self._row("WiFi SSID", self.isp.get("ssid", "—"))
        self._row("Spreadsheet", self.isp.get("spreadsheet_name", "—"))
        self._row("Interval", f"Every {self.isp.get('interval_hours', 2)}h")
        days = ", ".join(self.isp.get("active_days", [])) or "None"
        self._row("Active Days", days)

        ctk.CTkFrame(self, height=1, fg_color=BORDER).pack(fill="x", padx=12, pady=6)

        # Speed + next run
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="x", padx=12, pady=(0, 12))
        bottom.grid_columnconfigure(0, weight=1)
        bottom.grid_columnconfigure(1, weight=1)

        left = ctk.CTkFrame(bottom, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(left, text="Last Speed", font=ctk.CTkFont(size=10),
                     text_color=TEXT_MUTED).pack(anchor="w")
        self.speed_label = ctk.CTkLabel(
            left, text="—", font=ctk.CTkFont(size=22, weight="bold"),
            text_color=SUCCESS
        )
        self.speed_label.pack(anchor="w")

        right = ctk.CTkFrame(bottom, fg_color="transparent")
        right.grid(row=0, column=1, sticky="e")
        ctk.CTkLabel(right, text="Next Run", font=ctk.CTkFont(size=10),
                     text_color=TEXT_MUTED).pack(anchor="e")
        self.next_run_label = ctk.CTkLabel(
            right, text="—", font=ctk.CTkFont(size=12),
            text_color=TEXT_PRIMARY
        )
        self.next_run_label.pack(anchor="e")

        # Run now button
        ctk.CTkButton(
            self,
            text="▶  Run Now",
            fg_color=ACCENT,
            hover_color="#3a72d4",
            height=32,
            corner_radius=8,
            font=ctk.CTkFont(size=12),
            command=self._run_now
        ).pack(fill="x", padx=12, pady=(0, 12))

    def _row(self, label: str, value: str):
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=1)
        ctk.CTkLabel(row, text=label + ":", font=ctk.CTkFont(size=11),
                     text_color=TEXT_MUTED, width=100, anchor="w").pack(side="left")
        ctk.CTkLabel(row, text=value, font=ctk.CTkFont(size=11),
                     text_color=TEXT_PRIMARY, anchor="w").pack(side="left")

    def update_status(self, last_speed: str, next_run: str, is_active: bool):
        color = SUCCESS if is_active else TEXT_MUTED
        self.status_dot.configure(text_color=color)
        if last_speed:
            speed_color = DANGER if "NO" in last_speed.upper() else SUCCESS
            self.speed_label.configure(text=last_speed, text_color=speed_color)
        self.next_run_label.configure(text=next_run)

    def _run_now(self):
        scheduler.run_now(self.isp["id"])


class DashboardFrame(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=BG_DARK, **kwargs)
        self._cards: Dict[str, ISPCard] = {}
        self._build()
        self._start_refresh()

    def _build(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Header bar
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 0))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text="Dashboard",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=TEXT_PRIMARY
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            header, text="ISP speed monitoring overview",
            font=ctk.CTkFont(size=12), text_color=TEXT_MUTED
        ).grid(row=1, column=0, sticky="w")

        # Scheduler toggle
        ctrl = ctk.CTkFrame(header, fg_color="transparent")
        ctrl.grid(row=0, column=1, rowspan=2, sticky="e")

        self.scheduler_status = ctk.CTkLabel(
            ctrl, text="● Stopped", font=ctk.CTkFont(size=12),
            text_color=DANGER
        )
        self.scheduler_status.pack(side="left", padx=(0, 10))

        self.toggle_btn = ctk.CTkButton(
            ctrl, text="▶  Start Scheduler",
            fg_color=SUCCESS, hover_color="#3a8f5f",
            width=160, height=36, corner_radius=8,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._toggle_scheduler
        )
        self.toggle_btn.pack(side="left")

        ctk.CTkFrame(self, height=1, fg_color=BORDER).grid(
            row=0, column=0, sticky="ew", padx=24, pady=(60, 0)
        )

        # Cards scroll area
        self.scroll = ctk.CTkScrollableFrame(
            self, fg_color=BG_DARK, scrollbar_button_color=BORDER
        )
        self.scroll.grid(row=1, column=0, sticky="nsew", padx=16, pady=16)
        self.scroll.grid_columnconfigure((0, 1), weight=1)

        self._render_cards()

    def _render_cards(self):
        for widget in self.scroll.winfo_children():
            widget.destroy()
        self._cards.clear()

        isps = config_manager.get_isps()
        if not isps:
            ctk.CTkLabel(
                self.scroll,
                text="No ISPs configured.\nGo to ISP Config to add one.",
                font=ctk.CTkFont(size=14), text_color=TEXT_MUTED
            ).grid(row=0, column=0, columnspan=2, pady=60)
            return

        for i, isp in enumerate(isps):
            card = ISPCard(self.scroll, isp)
            card.grid(row=i // 2, column=i % 2, padx=8, pady=8, sticky="nsew")
            self._cards[isp["id"]] = card

    def _toggle_scheduler(self):
        if scheduler.is_running():
            scheduler.stop()
        else:
            scheduler.start()
        self._update_scheduler_ui()

    def _update_scheduler_ui(self):
        if scheduler.is_running():
            self.scheduler_status.configure(text="● Running", text_color=SUCCESS)
            self.toggle_btn.configure(
                text="⏹  Stop Scheduler", fg_color=DANGER, hover_color="#b04040"
            )
        else:
            self.scheduler_status.configure(text="● Stopped", text_color=DANGER)
            self.toggle_btn.configure(
                text="▶  Start Scheduler", fg_color=SUCCESS, hover_color="#3a8f5f"
            )

    def _start_refresh(self):
        """Refresh card data every 10 seconds."""
        self._refresh()
        self.after(10000, self._start_refresh)

    def _refresh(self):
        self._update_scheduler_ui()
        state = config_manager.load_state()

        for isp_id, card in self._cards.items():
            isp_state = state.get(isp_id, {})
            last_run_str = isp_state.get("last_run", "")
            last_speed = isp_state.get("last_speed", "—")

            next_run_text = "—"
            if last_run_str:
                try:
                    last_run = datetime.fromisoformat(last_run_str)
                    isp = config_manager.get_isp_by_id(isp_id)
                    if isp:
                        interval = isp.get("interval_hours", 2)
                        next_run = last_run + timedelta(hours=interval)
                        next_run_text = next_run.strftime("%I:%M %p")
                except Exception:
                    pass

            card.update_status(last_speed, next_run_text, scheduler.is_running())

    def on_show(self):
        self._render_cards()
        self._refresh()
