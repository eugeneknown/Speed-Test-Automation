import PyInstaller.__main__
import os

print("Starting build process...")

# Tell Playwright to install browsers in the local folder so PyInstaller can find them
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "0"
print("Ensuring Playwright Chromium is installed locally...")
os.system("python -m playwright install chromium")

print("Running PyInstaller...")
PyInstaller.__main__.run([
    'main.py',
    '--name=SpeedTestAutomation',
    '--onedir',          # Use a directory instead of a single massive .exe to keep it fast
    '--windowed',        # Hide the black console window
    '--noconfirm',       # Overwrite existing build
    '--hidden-import=googleapiclient',
    '--hidden-import=google_auth_oauthlib',
    '--hidden-import=customtkinter',
    '--hidden-import=pystray',
    '--hidden-import=PIL',
    '--hidden-import=apscheduler',
    '--collect-all=playwright',
    '--collect-all=customtkinter',
])

print("\n✅ Build complete! You can find the executable in the 'dist/SpeedTestAutomation' folder.")
