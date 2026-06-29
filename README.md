# 🚀 Multi-ISP SpeedTest Automator

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![Playwright](https://img.shields.io/badge/Playwright-Automated_Testing-green.svg)
![Google Cloud](https://img.shields.io/badge/Google_Cloud-Drive_%7C_Sheets-orange.svg)
![CustomTkinter](https://img.shields.io/badge/CustomTkinter-Modern_GUI-purple.svg)

An autonomous Windows desktop application built in Python that automatically tests, logs, and visually verifies internet speeds across multiple ISPs. Designed for small-to-medium network environments that require verifiable proof of SLAs (Service Level Agreements) and uptime.

## ✨ Features

- **Autonomous Network Switching**: Automatically interfaces with the Windows `netsh wlan` utility to disconnect and connect to specific ISP wireless networks on a scheduled basis.
- **Headless Speed Testing**: Utilizes **Playwright** to drive a headless Chromium browser instance to `fast.com`, waiting for network stabilization before capturing an automated screenshot of the results.
- **Automated Cloud Logging**: 
  - Authenticates securely via **Google OAuth 2.0 (Desktop Flow)**.
  - Uploads the proof-of-speed screenshot directly to a designated folder in Google Drive.
  - Automatically creates and formats a daily Google Sheet tab (e.g., `Jun 18 2026`).
  - Logs the timestamp, text speed result, and embeds the Drive screenshot directly into the sheet using `=IMAGE()` formulas.
- **Modern GUI Dashboard**: Built with **CustomTkinter** to provide a sleek, dark-mode-first user interface for managing ISP credentials, configuring test intervals (via `APScheduler`), and viewing real-time execution logs.
- **Resilient Polling**: Includes advanced retries (up to 5 connection attempts) to handle flaky Windows WiFi adapters, automatically declaring "NO CONNECTION" and logging the outage if a network is genuinely down.

## 🏗️ Architecture

The system is designed with a clean, modular architecture:

- `core/scheduler.py`: The heart of the automation. Uses `APScheduler` to trigger per-ISP test pipelines on background threads.
- `core/wifi_switcher.py`: Dynamically generates Windows XML WLAN profiles and executes socket-based connectivity checks.
- `core/speed_tester.py`: Playwright orchestration for interacting with modern, dynamic DOM elements.
- `core/sheets_logger.py` & `core/drive_uploader.py`: API wrappers for seamless Google Workspace integration.
- `gui/`: A decoupled UI layer that routes background worker logs to a thread-safe frontend viewer.

## 🚀 Installation & Setup

### Prerequisites
- Windows 10/11
- Python 3.11+
- A Google Cloud Project with the **Google Drive API** and **Google Sheets API** enabled.

### 1. Clone & Install
```bash
git clone https://github.com/yourusername/speedtest-automation.git
cd speedtest-automation
pip install -r requirements.txt
python -m playwright install chromium
```

### 2. Google OAuth Setup
1. Go to the [Google Cloud Console](https://console.cloud.google.com).
2. Enable the **Google Drive API** and **Google Sheets API**.
3. Create an **OAuth Consent Screen** (External).
4. Create Credentials -> **OAuth client ID** (Application Type: Desktop app).
5. Download the `.json` client secret file.

### 3. Run the Application
```bash
python main.py
```
1. Navigate to the **Settings** tab in the GUI.
2. Select your downloaded OAuth JSON file.
3. Click **Run Full Configuration Test** to authorize the application via your browser and verify cloud connectivity.
4. Add your ISPs in the **ISP Config** tab and click **Start Scheduler**!

## 📦 Building for Production

This project includes an automated build script to package the application and bundle the Playwright Chromium browser into a distributable Windows package using PyInstaller:

```bash
python build_exe.py
```
The resulting package will be available in the `dist/SpeedTestAutomation/` directory.

## 📄 License
This project is licensed under the MIT License.
