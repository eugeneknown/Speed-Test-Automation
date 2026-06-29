"""
isp_config.py
ISP configuration screen — list all ISPs, add/edit/delete with a form dialog.
"""

import uuid
import customtkinter as ctk
from tkinter import messagebox
from core import config_manager, scheduler

BG_DARK   = "#0f1117"
BG_CARD   = "#1c2333"
BG_CARD2  = "#202840"
ACCENT    = "#4f8ef7"
TEXT_PRIMARY = "#e8eaf6"
TEXT_MUTED   = "#7b8db0"
SUCCESS   = "#4caf7d"
DANGER    = "#e05c5c"
BORDER    = "#2a3250"

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
INTERVALS = [1, 2, 3, 4, 6, 12]


class ISPFormDialog(ctk.CTkToplevel):
    """Modal dialog for adding or editing an ISP configuration."""

    def __init__(self, master, isp: dict = None, on_save=None):
        super().__init__(master)
        self.isp = isp or config_manager.new_isp_template()
        self.on_save = on_save
        self.title("Edit ISP" if isp else "Add ISP")
        self.geometry("520x680")
        self.resizable(False, False)
        self.configure(fg_color=BG_DARK)
        self.grab_set()
        self._build()

    def _build(self):
        container = ctk.CTkScrollableFrame(self, fg_color=BG_DARK)
        container.pack(fill="both", expand=True, padx=20, pady=20)

        def section(text):
            ctk.CTkLabel(
                container, text=text,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=ACCENT
            ).pack(anchor="w", pady=(12, 2))
            ctk.CTkFrame(container, height=1, fg_color=BORDER).pack(fill="x", pady=(0, 8))

        def field(label, var, placeholder="", show=""):
            ctk.CTkLabel(container, text=label, font=ctk.CTkFont(size=11),
                         text_color=TEXT_MUTED).pack(anchor="w")
            entry = ctk.CTkEntry(
                container, textvariable=var, placeholder_text=placeholder,
                fg_color=BG_CARD, border_color=BORDER, text_color=TEXT_PRIMARY,
                height=36, show=show
            )
            entry.pack(fill="x", pady=(2, 8))
            return entry

        # ── ISP Identity ──────────────────────────────────────────────────────
        section("ISP Identity")
        self.v_name = ctk.StringVar(value=self.isp.get("name", ""))
        field("ISP Name *", self.v_name, "e.g. Globe Fiber")

        self.v_ssid = ctk.StringVar(value=self.isp.get("ssid", ""))
        field("WiFi SSID *", self.v_ssid, "e.g. Globe_Home_5G")

        self.v_password = ctk.StringVar(value=self.isp.get("password", ""))
        field("WiFi Password", self.v_password, "Leave blank for open networks", show="●")

        # ── Google Sheets ─────────────────────────────────────────────────────
        section("Google Sheets")
        self.v_sheet = ctk.StringVar(value=self.isp.get("spreadsheet_name", ""))
        field("Spreadsheet Name *", self.v_sheet, "e.g. Globe Speed Log")

        self.v_url = ctk.StringVar(value=self.isp.get("speed_test_url", "https://fast.com"))
        field("Speed Test URL", self.v_url, "https://fast.com")

        # ── Schedule ──────────────────────────────────────────────────────────
        section("Schedule")
        ctk.CTkLabel(container, text="Recording Interval",
                     font=ctk.CTkFont(size=11), text_color=TEXT_MUTED).pack(anchor="w")

        self.v_interval = ctk.StringVar(
            value=f"Every {self.isp.get('interval_hours', 2)} Hours"
        )
        interval_menu = ctk.CTkOptionMenu(
            container,
            values=[f"Every {h} Hour{'s' if h > 1 else ''}" for h in INTERVALS],
            variable=self.v_interval,
            fg_color=BG_CARD, button_color=ACCENT,
            dropdown_fg_color=BG_CARD, text_color=TEXT_PRIMARY,
            height=36
        )
        interval_menu.pack(fill="x", pady=(2, 12))

        ctk.CTkLabel(container, text="Active Days",
                     font=ctk.CTkFont(size=11), text_color=TEXT_MUTED).pack(anchor="w")

        days_frame = ctk.CTkFrame(container, fg_color=BG_CARD, corner_radius=8)
        days_frame.pack(fill="x", pady=(2, 12))

        self.day_vars = {}
        active_days = self.isp.get("active_days", DAYS[:5])
        for i, day in enumerate(DAYS):
            var = ctk.BooleanVar(value=day in active_days)
            self.day_vars[day] = var
            row = i // 4
            col = i % 4
            ctk.CTkCheckBox(
                days_frame, text=day[:3], variable=var,
                text_color=TEXT_PRIMARY, fg_color=ACCENT,
                hover_color="#3a72d4", font=ctk.CTkFont(size=11)
            ).grid(row=row, column=col, padx=12, pady=8, sticky="w")

        # ── Enable toggle ─────────────────────────────────────────────────────
        ctk.CTkFrame(container, height=1, fg_color=BORDER).pack(fill="x", pady=8)
        self.v_enabled = ctk.BooleanVar(value=self.isp.get("enabled", True))
        ctk.CTkSwitch(
            container, text="Enable this ISP",
            variable=self.v_enabled,
            text_color=TEXT_PRIMARY, progress_color=ACCENT,
            font=ctk.CTkFont(size=12)
        ).pack(anchor="w", pady=4)

        # ── Action buttons ────────────────────────────────────────────────────
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(0, 20))

        ctk.CTkButton(
            btn_frame, text="Cancel",
            fg_color=BG_CARD, hover_color=BG_CARD2,
            text_color=TEXT_MUTED, width=120, height=38,
            command=self.destroy
        ).pack(side="left")

        ctk.CTkButton(
            btn_frame, text="💾  Save ISP",
            fg_color=ACCENT, hover_color="#3a72d4",
            width=160, height=38,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._save
        ).pack(side="right")

    def _save(self):
        name = self.v_name.get().strip()
        ssid = self.v_ssid.get().strip()
        sheet = self.v_sheet.get().strip()

        if not name or not ssid or not sheet:
            messagebox.showerror("Validation Error",
                                 "ISP Name, WiFi SSID, and Spreadsheet Name are required.",
                                 parent=self)
            return

        # Parse interval
        interval_str = self.v_interval.get()
        interval_hours = int(interval_str.split()[1])

        active_days = [d for d, v in self.day_vars.items() if v.get()]
        if not active_days:
            messagebox.showerror("Validation Error",
                                 "Please select at least one active day.",
                                 parent=self)
            return

        self.isp.update({
            "name": name,
            "ssid": ssid,
            "password": self.v_password.get(),
            "spreadsheet_name": sheet,
            "speed_test_url": self.v_url.get().strip() or "https://fast.com",
            "interval_hours": interval_hours,
            "active_days": active_days,
            "enabled": self.v_enabled.get()
        })

        config_manager.save_isp(self.isp)
        if scheduler.is_running():
            scheduler.restart()

        if self.on_save:
            self.on_save()
        self.destroy()


class ISPRow(ctk.CTkFrame):
    """A single row representing an ISP in the list."""

    def __init__(self, master, isp: dict, on_edit, on_delete, **kwargs):
        super().__init__(master, fg_color=BG_CARD, corner_radius=10, **kwargs)
        self.isp = isp
        self.configure(border_width=1, border_color=BORDER)

        self.grid_columnconfigure(1, weight=1)

        # Status indicator
        color = SUCCESS if isp.get("enabled", True) else DANGER
        ctk.CTkLabel(self, text="●", text_color=color,
                     font=ctk.CTkFont(size=16)).grid(row=0, column=0, padx=(16, 8), pady=16)

        # ISP info
        info = ctk.CTkFrame(self, fg_color="transparent")
        info.grid(row=0, column=1, sticky="ew", pady=12)

        ctk.CTkLabel(info, text=isp["name"],
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=TEXT_PRIMARY, anchor="w").pack(anchor="w")
        ctk.CTkLabel(
            info,
            text=f"SSID: {isp.get('ssid', '—')}  •  "
                 f"Sheet: {isp.get('spreadsheet_name', '—')}  •  "
                 f"Every {isp.get('interval_hours', 2)}h  •  "
                 f"{', '.join(isp.get('active_days', [])[:3])}{'...' if len(isp.get('active_days', [])) > 3 else ''}",
            font=ctk.CTkFont(size=11), text_color=TEXT_MUTED, anchor="w"
        ).pack(anchor="w")

        # Action buttons
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=0, column=2, padx=12)

        ctk.CTkButton(
            actions, text="Edit", width=70, height=32,
            fg_color=ACCENT, hover_color="#3a72d4",
            font=ctk.CTkFont(size=12),
            command=lambda: on_edit(isp)
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            actions, text="Delete", width=70, height=32,
            fg_color=DANGER, hover_color="#b04040",
            font=ctk.CTkFont(size=12),
            command=lambda: on_delete(isp)
        ).pack(side="left", padx=4)


class ISPConfigFrame(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=BG_DARK, **kwargs)
        self._build()

    def _build(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 0))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header, text="ISP Configuration",
                     font=ctk.CTkFont(size=24, weight="bold"),
                     text_color=TEXT_PRIMARY).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(header, text="Add and manage your internet service providers",
                     font=ctk.CTkFont(size=12), text_color=TEXT_MUTED
                     ).grid(row=1, column=0, sticky="w")

        ctk.CTkButton(
            header, text="＋  Add ISP",
            fg_color=ACCENT, hover_color="#3a72d4",
            width=140, height=38, corner_radius=8,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._add_isp
        ).grid(row=0, column=1, rowspan=2, sticky="e")

        ctk.CTkFrame(self, height=1, fg_color=BORDER).grid(
            row=0, column=0, sticky="ew", padx=24, pady=(62, 0)
        )

        # List
        self.list_frame = ctk.CTkScrollableFrame(
            self, fg_color=BG_DARK, scrollbar_button_color=BORDER
        )
        self.list_frame.grid(row=1, column=0, sticky="nsew", padx=16, pady=12)
        self.list_frame.grid_columnconfigure(0, weight=1)

        self._render_list()

    def _render_list(self):
        for w in self.list_frame.winfo_children():
            w.destroy()

        isps = config_manager.get_isps()
        if not isps:
            ctk.CTkLabel(
                self.list_frame,
                text="No ISPs configured yet.\nClick '＋ Add ISP' to get started.",
                font=ctk.CTkFont(size=14), text_color=TEXT_MUTED
            ).grid(row=0, column=0, pady=60)
            return

        for i, isp in enumerate(isps):
            ISPRow(
                self.list_frame, isp,
                on_edit=self._edit_isp,
                on_delete=self._delete_isp
            ).grid(row=i, column=0, sticky="ew", padx=8, pady=6)

    def _add_isp(self):
        ISPFormDialog(self, on_save=self._render_list)

    def _edit_isp(self, isp: dict):
        ISPFormDialog(self, isp=isp, on_save=self._render_list)

    def _delete_isp(self, isp: dict):
        confirmed = messagebox.askyesno(
            "Delete ISP",
            f"Are you sure you want to delete '{isp['name']}'?\nThis cannot be undone.",
            parent=self
        )
        if confirmed:
            config_manager.delete_isp(isp["id"])
            if scheduler.is_running():
                scheduler.restart()
            self._render_list()

    def on_show(self):
        self._render_list()
