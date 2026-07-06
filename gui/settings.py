"""
settings.py
Settings screen — Google Service Account credentials path,
Drive folder name, and a built-in Service Account setup guide.
"""

import threading
import os
import sys
import customtkinter as ctk
from tkinter import filedialog, messagebox
from core import config_manager, tester

BG_DARK   = "#0f1117"
BG_CARD   = "#1c2333"
BG_CARD2  = "#202840"
ACCENT    = "#4f8ef7"
TEXT_PRIMARY = "#e8eaf6"
TEXT_MUTED   = "#7b8db0"
SUCCESS   = "#4caf7d"
DANGER    = "#e05c5c"
BORDER    = "#2a3250"

SETUP_GUIDE = """
STEP 1 — Create a Google Cloud Project
  1. Go to https://console.cloud.google.com
  2. Click "Select a project" → "New Project"
  3. Name it (e.g. SpeedTest Automation) → Click "Create"

STEP 2 — Enable Required APIs
  1. Go to APIs & Services → Library
  2. Search "Google Sheets API" → Click it → Click the blue "Enable" button
  3. Search "Google Drive API" → Click it → Click the blue "Enable" button
  * NOTE: If the app gives a "403 Forbidden" error, it means 
    these APIs are not enabled. After clicking Enable, wait 
    1-2 minutes for Google's systems to update!

STEP 3 — Configure OAuth Consent Screen
  1. Go to APIs & Services → OAuth consent screen
  2. Choose "External" → "Create"
  3. App Name: "SpeedTest", User Support Email: <your email>
  4. Developer Contact Info: <your email>
  5. Click "Save and Continue" through Scopes and Test Users
  6. On the Summary page, click "Publish App" (so the token doesn't expire)

STEP 4 — Create OAuth Client ID
  1. Go to APIs & Services → Credentials
  2. Click "+ Create Credentials" → "OAuth client ID"
  3. Application Type: "Desktop app"
  4. Name: "SpeedTest Desktop" → Click "Create"
  5. Click "Download JSON" on the popup.
  6. Save the downloaded .json file somewhere safe

STEP 5 — Configure the App
  1. In this Settings screen, click "Browse" next to
     "Credentials JSON Path"
  2. Select the downloaded OAuth Client ID .json file
  3. Click "Save Settings"
  4. Run the Full Configuration Test. A browser window will open
     asking you to log in with your Gmail account!

✅  That's it! The app will manage all spreadsheets under your personal Google Drive automatically.
""".strip()


class ConfigTestDialog(ctk.CTkToplevel):
    """Modal dialog to run and display the end-to-end config test."""

    def __init__(self, master, credentials_path: str, drive_folder: str):
        super().__init__(master)
        self.credentials_path = credentials_path
        self.drive_folder = drive_folder
        
        self.title("Configuration Test")
        self.geometry("550x500")
        self.resizable(False, False)
        self.configure(fg_color=BG_DARK)
        self.grab_set()

        self._labels = []
        self._build()
        self._start_test()

    def _build(self):
        container = ctk.CTkFrame(self, fg_color=BG_DARK)
        container.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            container, text="End-to-End Configuration Test",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=TEXT_PRIMARY
        ).pack(anchor="w", pady=(0, 4))
        
        ctk.CTkLabel(
            container, text="Running tests in the background. Please wait...",
            font=ctk.CTkFont(size=12), text_color=TEXT_MUTED
        ).pack(anchor="w", pady=(0, 16))

        # Create rows for each step
        self.steps_frame = ctk.CTkFrame(container, fg_color=BG_CARD, corner_radius=8, border_width=1, border_color=BORDER)
        self.steps_frame.pack(fill="both", expand=True)

        for i, step_name in enumerate(tester.STEPS):
            row = ctk.CTkFrame(self.steps_frame, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=12)
            
            icon = ctk.CTkLabel(row, text="⏳", font=ctk.CTkFont(size=16), text_color=TEXT_MUTED, width=24)
            icon.pack(side="left")
            
            text_frame = ctk.CTkFrame(row, fg_color="transparent")
            text_frame.pack(side="left", fill="x", expand=True, padx=12)
            
            title = ctk.CTkLabel(text_frame, text=step_name, font=ctk.CTkFont(size=12, weight="bold"), text_color=TEXT_PRIMARY, anchor="w")
            title.pack(fill="x")
            
            detail = ctk.CTkLabel(text_frame, text="Pending...", font=ctk.CTkFont(size=11), text_color=TEXT_MUTED, anchor="w")
            detail.pack(fill="x")
            
            self._labels.append({"icon": icon, "title": title, "detail": detail})

        self.close_btn = ctk.CTkButton(
            container, text="Close", width=120, height=36,
            fg_color=BG_CARD, hover_color=BG_CARD2, text_color=TEXT_MUTED,
            command=self.destroy, state="disabled"
        )
        self.close_btn.pack(pady=(20, 0))

    def _start_test(self):
        # Start in background thread
        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()

    def _run(self):
        def on_step(index: int, success: bool, detail: str):
            # Schedule UI update on main thread
            self.after(0, self._update_step, index, success, detail)
        
        tester.run_all_tests(
            self.credentials_path,
            self.drive_folder,
            "SpeedTest Config Test",
            on_step
        )
        
        # Enable close button when done
        self.after(0, lambda: self.close_btn.configure(state="normal", fg_color=ACCENT, hover_color="#3a72d4", text_color="white"))

    def _update_step(self, index: int, success: bool, detail_text: str):
        if index < len(self._labels):
            lbls = self._labels[index]
            lbls["icon"].configure(text="✅" if success else "❌")
            lbls["title"].configure(text_color=SUCCESS if success else DANGER)
            lbls["detail"].configure(text=detail_text)


class SettingsFrame(ctk.CTkFrame):
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

        ctk.CTkLabel(
            header, text="Settings",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=TEXT_PRIMARY
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            header, text="Configure Google credentials and app preferences",
            font=ctk.CTkFont(size=12), text_color=TEXT_MUTED
        ).grid(row=1, column=0, sticky="w")

        ctk.CTkFrame(self, height=1, fg_color=BORDER).grid(
            row=0, column=0, sticky="ew", padx=24, pady=(62, 0)
        )

        # Scroll container
        scroll = ctk.CTkScrollableFrame(self, fg_color=BG_DARK, scrollbar_button_color=BORDER)
        scroll.grid(row=1, column=0, sticky="nsew", padx=16, pady=12)
        scroll.grid_columnconfigure(0, weight=1)

        # ── Google Credentials Section ────────────────────────────────────────
        self._section_label(scroll, "🔑  Google OAuth Client ID")

        cred_frame = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=10,
                                   border_width=1, border_color=BORDER)
        cred_frame.grid(row=1, column=0, sticky="ew", padx=8, pady=(4, 16))
        cred_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(cred_frame, text="Credentials JSON Path",
                     font=ctk.CTkFont(size=11), text_color=TEXT_MUTED
                     ).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 2))

        path_row = ctk.CTkFrame(cred_frame, fg_color="transparent")
        path_row.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 14))
        path_row.grid_columnconfigure(0, weight=1)

        self.v_cred_path = ctk.StringVar(value=config_manager.get_service_account_path())
        ctk.CTkEntry(
            path_row, textvariable=self.v_cred_path,
            placeholder_text="Click Browse to select credentials.json",
            fg_color=BG_CARD2, border_color=BORDER, text_color=TEXT_PRIMARY,
            height=36
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkButton(
            path_row, text="Browse", width=90, height=36,
            fg_color=ACCENT, hover_color="#3a72d4",
            command=self._browse_credentials
        ).grid(row=0, column=1)

        # Validate button
        ctk.CTkButton(
            cred_frame, text="✔  Validate Credentials",
            fg_color="transparent", hover_color=BG_CARD2,
            text_color=TEXT_MUTED, border_width=1, border_color=BORDER,
            height=32, corner_radius=6, font=ctk.CTkFont(size=11),
            command=self._validate_credentials
        ).grid(row=2, column=0, sticky="w", padx=16, pady=(0, 14))

        self.cred_status = ctk.CTkLabel(cred_frame, text="",
                                         font=ctk.CTkFont(size=11),
                                         text_color=TEXT_MUTED)
        self.cred_status.grid(row=3, column=0, sticky="w", padx=16, pady=(0, 10))

        # Full Test Button
        ctk.CTkButton(
            cred_frame, text="🚀  Run Full Configuration Test",
            fg_color="#3d5a8a", hover_color="#2c4266",
            text_color="white", height=32, corner_radius=6, font=ctk.CTkFont(size=11, weight="bold"),
            command=self._run_full_test
        ).grid(row=2, column=0, sticky="e", padx=16, pady=(0, 14))

        # ── Startup Preferences ──────────────────────────────────────────────────
        self._section_label(scroll, "⚙️  Startup Preferences", row=4)

        startup_frame = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=10,
                                      border_width=1, border_color=BORDER)
        startup_frame.grid(row=5, column=0, sticky="ew", padx=8, pady=(4, 16))

        cfg = config_manager.load_config()
        self.v_run_startup = ctk.BooleanVar(value=cfg.get("run_on_startup", False))
        self.v_auto_start = ctk.BooleanVar(value=cfg.get("auto_start_scheduler", False))

        ctk.CTkSwitch(
            startup_frame, text="Run app automatically when Windows starts",
            variable=self.v_run_startup, onvalue=True, offvalue=False,
            progress_color=ACCENT, text_color=TEXT_PRIMARY, font=ctk.CTkFont(size=12)
        ).pack(anchor="w", padx=16, pady=(16, 8))

        ctk.CTkSwitch(
            startup_frame, text="Start scheduler immediately when app launches",
            variable=self.v_auto_start, onvalue=True, offvalue=False,
            progress_color=ACCENT, text_color=TEXT_PRIMARY, font=ctk.CTkFont(size=12)
        ).pack(anchor="w", padx=16, pady=(8, 16))

        # ── Auto Updates ───────────────────────────────────────────────────────
        self._section_label(scroll, "🔄  Software Updates", row=6)
        
        update_frame = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BORDER)
        update_frame.grid(row=7, column=0, sticky="ew", padx=8, pady=(4, 16))
        
        from core.version import __version__
        self.lbl_version = ctk.CTkLabel(update_frame, text=f"Current Version: v{__version__}", font=ctk.CTkFont(size=12), text_color=TEXT_PRIMARY)
        self.lbl_version.pack(anchor="w", padx=16, pady=(16, 8))
        
        self.btn_check_update = ctk.CTkButton(
            update_frame, text="Check for Updates", fg_color=BG_CARD2, hover_color="#2a3250", border_width=1, border_color=BORDER, text_color=TEXT_PRIMARY, height=32, corner_radius=6,
            command=self._manual_check_update
        )
        self.btn_check_update.pack(anchor="w", padx=16, pady=(0, 16))

        # ── Save button ────────────────────────────────────────────────────────
        ctk.CTkButton(
            scroll, text="💾  Save Settings",
            fg_color=ACCENT, hover_color="#3a72d4",
            height=42, corner_radius=8,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._save
        ).grid(row=8, column=0, sticky="ew", padx=8, pady=(4, 24))

        # ── Service Account Setup Guide ────────────────────────────────────────
        self._section_label(scroll, "📖  Google Service Account Setup Guide", row=9)

        guide_frame = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=10,
                                    border_width=1, border_color=BORDER)
        guide_frame.grid(row=10, column=0, sticky="ew", padx=8, pady=(4, 24))

        ctk.CTkTextbox(
            guide_frame,
            text_color=TEXT_MUTED,
            fg_color="transparent",
            font=ctk.CTkFont(family="Consolas", size=11),
            wrap="word",
            height=320,
            state="normal"
        ).pack(fill="both", expand=True, padx=4, pady=4)

        # Insert guide text
        guide_box = guide_frame.winfo_children()[0]
        guide_box.insert("1.0", SETUP_GUIDE)
        guide_box.configure(state="disabled")

    def _section_label(self, parent, text: str, row: int = 0):
        ctk.CTkLabel(
            parent, text=text,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=ACCENT
        ).grid(row=row, column=0, sticky="w", padx=8, pady=(16, 2))

    def _browse_credentials(self):
        path = filedialog.askopenfilename(
            title="Select Service Account Credentials",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if path:
            self.v_cred_path.set(path)

    def _validate_credentials(self):
        path = self.v_cred_path.get().strip()
        if not path:
            self.cred_status.configure(text="⚠ No file selected.", text_color=WARNING if False else "#f5a623")
            return
        try:
            import json
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "installed" in data or "web" in data:
                self.cred_status.configure(
                    text="✅ Valid OAuth Client ID file",
                    text_color=SUCCESS
                )
            else:
                self.cred_status.configure(
                    text="❌ Invalid JSON: missing 'installed' or 'web'",
                    text_color=DANGER
                )
        except Exception as e:
            self.cred_status.configure(
                text=f"❌ Invalid credentials: {e}",
                text_color=DANGER
            )

    def _manual_check_update(self):
        self.btn_check_update.configure(state="disabled", text="Checking...")
        
        def run_check():
            from core import updater
            update_info = updater.check_for_updates()
            self.after(0, self._on_update_checked, update_info)
            
        threading.Thread(target=run_check, daemon=True).start()
        
    def _on_update_checked(self, update_info):
        self.btn_check_update.configure(state="normal", text="Check for Updates")
        if not update_info:
            messagebox.showinfo("Updates", "You are running the latest version!", parent=self)
            return
            
        ver = update_info["version"]
        msg = f"A new version (v{ver}) is available!\n\nDo you want to download and install it now?"
        if messagebox.askyesno("Update Available", msg, parent=self):
            self._download_update(update_info["download_url"])
            
    def _download_update(self, url):
        self.btn_check_update.configure(state="disabled", text="Downloading... 0%")
        
        def update_progress(pct):
            self.after(0, lambda: self.btn_check_update.configure(text=f"Downloading... {pct}%"))
            
        def run_download():
            from core import updater
            success = updater.download_and_install_update(url, update_progress)
            if not success:
                self.after(0, lambda: messagebox.showerror("Update Failed", "Failed to download or install the update.\nEnsure you are running the built .exe and try again.", parent=self))
                self.after(0, lambda: self.btn_check_update.configure(state="normal", text="Check for Updates"))
                
        threading.Thread(target=run_download, daemon=True).start()

    def _apply_startup_registry(self, enable: bool):
        """Create or remove a shortcut in the Windows Startup folder."""
        try:
            import win32com.client
            startup_dir = os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
            shortcut_path = os.path.join(startup_dir, "SpeedTestAutomation.lnk")
            
            if enable:
                if getattr(sys, 'frozen', False):
                    target = sys.executable
                else:
                    target = os.path.abspath(sys.argv[0])
                    
                shell = win32com.client.Dispatch("WScript.Shell")
                shortcut = shell.CreateShortCut(shortcut_path)
                shortcut.Targetpath = target
                shortcut.WorkingDirectory = os.path.dirname(target)
                shortcut.IconLocation = target
                shortcut.save()
            else:
                if os.path.exists(shortcut_path):
                    os.remove(shortcut_path)
        except Exception as e:
            print(f"Failed to set startup shortcut: {e}")

    def _save(self):
        path = self.v_cred_path.get().strip()
        folder = self.v_drive_folder.get().strip() or "SpeedTest Results"
        run_startup = self.v_run_startup.get()
        auto_start = self.v_auto_start.get()

        config_manager.set_service_account_path(path)
        cfg = config_manager.load_config()
        cfg["drive_folder_name"] = folder
        cfg["run_on_startup"] = run_startup
        cfg["auto_start_scheduler"] = auto_start
        config_manager.save_config(cfg)
        
        # Apply windows startup
        self._apply_startup_registry(run_startup)

        messagebox.showinfo("Settings Saved", "Settings have been saved successfully.", parent=self)

    def _run_full_test(self):
        path = self.v_cred_path.get().strip()
        folder = self.v_drive_folder.get().strip() or "SpeedTest Results"
        
        if not path:
            messagebox.showerror("Error", "Please select an OAuth Client ID JSON file first.", parent=self)
            return
            
        ConfigTestDialog(self, path, folder)

    def on_show(self):
        cfg = config_manager.load_config()
        self.v_cred_path.set(cfg.get("service_account_path", ""))
        self.v_drive_folder.set(cfg.get("drive_folder_name", "SpeedTest Results"))
        self.v_run_startup.set(cfg.get("run_on_startup", False))
        self.v_auto_start.set(cfg.get("auto_start_scheduler", False))
