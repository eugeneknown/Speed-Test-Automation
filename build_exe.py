import PyInstaller.__main__
import os
import glob

print("Starting build process...")

# Tell Playwright to install browsers in the local folder so PyInstaller can find them
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "0"
print("Ensuring Playwright Chromium is installed locally...")
os.system("python -m playwright install chromium")

print("Running PyInstaller...")

args = [
    'main.py',
    '--name=SpeedTestAutomation',
    '--onefile',         # Build a standalone executable
    '--windowed',        # Hide the black console window
    '--icon=icon.ico',   # Application icon
    '--noconfirm',       # Overwrite existing build
    '--hidden-import=googleapiclient',
    '--hidden-import=google_auth_oauthlib',
    '--hidden-import=customtkinter',
    '--hidden-import=pystray',
    '--hidden-import=PIL',
    '--hidden-import=apscheduler',
    '--collect-all=playwright',
    '--collect-all=customtkinter',
]

# Bundle any client_secret*.json files found in the project root
_secrets = glob.glob('client_secret*.json')
if _secrets:
    for _f in _secrets:
        args.append(f'--add-data={_f};.')
        print(f"  Bundling credentials file: {_f}")
else:
    print("  ⚠️  No client_secret*.json found in project root — skipping bundle.")

PyInstaller.__main__.run(args)


print("\n✅ Build complete! You can find the executable in the 'dist/SpeedTestAutomation' folder.")
