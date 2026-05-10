"""
Creates a self-contained Externo Browser installer package:
  installer_output/
    Externo Browser.zip          <- all browser files (also upload to GitHub release)
    Install Externo Browser.bat  <- friend double-clicks this

Also updates version.json which you push to GitHub so existing users
get the update notification automatically.
"""
import os, sys, zipfile, pathlib, json, re

ROOT  = pathlib.Path(__file__).parent
SRC   = ROOT / "dist" / "Externo Browser"
OUT   = ROOT / "installer_output"
ZIP   = OUT / "Externo Browser.zip"
BAT   = OUT / "Install Externo Browser.bat"
VER_FILE = ROOT / "version.json"

if not SRC.exists():
    print(f"ERROR: Build folder not found: {SRC}")
    print("Run PyInstaller first, then re-run this script.")
    sys.exit(1)

# ── Ask for version and release notes ─────────────────────────────────────────
try:
    cur_ver = json.loads(VER_FILE.read_text())["version"]
except Exception:
    cur_ver = "1.0.0"

print(f"\nCurrent version: {cur_ver}")
new_ver = input("New version number (e.g. 1.0.1): ").strip()
if not re.match(r"^\d+\.\d+\.\d+$", new_ver):
    print("Invalid version format. Use X.Y.Z  (e.g. 1.2.0)")
    sys.exit(1)
notes = input("Release notes (shown in update banner): ").strip() or "Bug fixes and improvements"

GITHUB_USER = "kbnspacecmd"
GITHUB_REPO = "browser"
RELEASE_TAG = f"v{new_ver}"
RELEASE_ZIP = "Externo.Browser.zip"   # name you use when uploading to GitHub
download_url = f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}/releases/download/{RELEASE_TAG}/{RELEASE_ZIP}"

OUT.mkdir(exist_ok=True)

# ── Step 1: Zip the browser folder ────────────────────────────────────────────
print("Zipping browser files...")
if ZIP.exists():
    ZIP.unlink()

with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
    for file in SRC.rglob("*"):
        if file.is_file():
            arcname = "Externo Browser/" + str(file.relative_to(SRC))
            zf.write(file, arcname)
            print(f"  + {arcname}")

size_mb = ZIP.stat().st_size / 1_048_576
print(f"\nZip created: {ZIP}  ({size_mb:.1f} MB)")

# ── Step 2: Write the batch installer ─────────────────────────────────────────
bat_content = r"""@echo off
title Externo Browser Installer
color 0B
echo.
echo  =========================================
echo   EXTERNO BROWSER - Installer
echo  =========================================
echo.

:: Check zip exists
if not exist "%~dp0Externo Browser.zip" (
    echo ERROR: "Externo Browser.zip" not found next to this file.
    pause & exit /b 1
)

set INSTALL_DIR=%LOCALAPPDATA%\Externo Browser
set EXE=%INSTALL_DIR%\Externo Browser\Externo Browser.exe
set DESKTOP=%USERPROFILE%\Desktop
set STARTMENU=%APPDATA%\Microsoft\Windows\Start Menu\Programs

echo Installing to: %INSTALL_DIR%
echo.

:: Remove old install
if exist "%INSTALL_DIR%" (
    echo Removing previous version...
    rd /s /q "%INSTALL_DIR%"
)
mkdir "%INSTALL_DIR%"

:: Extract zip using PowerShell
echo Extracting files...
powershell -NoProfile -Command ^
  "Expand-Archive -LiteralPath '%~dp0Externo Browser.zip' -DestinationPath '%INSTALL_DIR%' -Force"

if not exist "%EXE%" (
    echo.
    echo ERROR: Extraction failed. Please try running as Administrator.
    pause & exit /b 1
)

:: Desktop shortcut
echo Creating desktop shortcut...
powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell; $sc = $ws.CreateShortcut('%DESKTOP%\Externo Browser.lnk'); $sc.TargetPath = '%EXE%'; $sc.WorkingDirectory = '%INSTALL_DIR%\Externo Browser'; $sc.IconLocation = '%EXE%'; $sc.Save()"

:: Start Menu shortcut
echo Creating Start Menu shortcut...
if not exist "%STARTMENU%\Externo Browser" mkdir "%STARTMENU%\Externo Browser"
powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell; $sc = $ws.CreateShortcut('%STARTMENU%\Externo Browser\Externo Browser.lnk'); $sc.TargetPath = '%EXE%'; $sc.WorkingDirectory = '%INSTALL_DIR%\Externo Browser'; $sc.IconLocation = '%EXE%'; $sc.Save()"

echo.
echo  =========================================
echo   Installation complete!
echo   Shortcut added to your Desktop and Start Menu.
echo  =========================================
echo.
set /p LAUNCH="Launch Externo Browser now? (Y/N): "
if /i "%LAUNCH%"=="Y" start "" "%EXE%"
echo.
pause
"""

BAT.write_text(bat_content)
print(f"Installer batch created: {BAT}")

# ── Step 3: Update version.json ───────────────────────────────────────────────
ver_data = {"version": new_ver, "download_url": download_url, "notes": notes}
VER_FILE.write_text(json.dumps(ver_data, indent=2) + "\n")
print(f"version.json updated  →  v{new_ver}")

print()
print("=" * 60)
print("DONE!")
print()
print("To release the update:")
print(f"  1. Rename {ZIP.name!r} → 'Externo.Browser.zip'")
print(f"  2. Create GitHub release tagged '{RELEASE_TAG}'")
print(f"     https://github.com/{GITHUB_USER}/{GITHUB_REPO}/releases/new")
print(f"  3. Upload 'Externo.Browser.zip' as a release asset")
print(f"  4. Commit & push version.json to your GitHub repo")
print()
print("Existing users will see the update banner automatically!")
print("=" * 60)
