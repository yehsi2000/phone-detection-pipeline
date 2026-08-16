import os
import sys
import platform
from pathlib import Path
import logging

logging.basicConfig(level=logging.CRITICAL+1, format='%(asctime)s %(levelname)s:%(message)s')
logger = logging.getLogger(__name__)

APP_NAME = "phone_detection_app"

def get_project_main_path() -> Path:
    """
    Returns the path to main.py, assuming it is located
    in the project root 2 levels above the current file.
    """
    current_file = Path(__file__).resolve()
    project_root = current_file.parents[2]  # two levels up
    main_path = project_root / "main.py"

    if not main_path.exists():
        raise FileNotFoundError(f"main.py not found at path: {main_path}")

    return main_path

def enable_autostart(app_name: str, script_path: str):
    """
    Adds a Python script to autostart, if it is not already added.

    :param app_name: Application name (unique, used as the shortcut/file name)
    :param script_path: Full path to the .py script
    """
    system = platform.system()

    if not os.path.isfile(script_path):
        raise ValueError(f"File not found: {script_path}")

    python_exe = sys.executable
    command = f'"{python_exe}" "{script_path}"'

    if system == "Windows":
        import win32com.client

        startup_dir = os.path.join(os.getenv('APPDATA'), r'Microsoft\Windows\Start Menu\Programs\Startup')
        shortcut_path = os.path.join(startup_dir, f"{app_name}.lnk")

        if os.path.exists(shortcut_path):
            logger.debug(f"[i] Already in autostart (Windows): {shortcut_path}")
            return

        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(shortcut_path)
        shortcut.Targetpath = python_exe
        shortcut.Arguments = f'"{script_path}"'
        shortcut.WorkingDirectory = os.path.dirname(script_path)
        shortcut.save()
        logger.debug(f"[✓] Added to autostart (Windows): {shortcut_path}")

    elif system == "Linux":
        autostart_dir = Path.home() / ".config" / "autostart"
        desktop_file = autostart_dir / f"{app_name}.desktop"

        if desktop_file.exists():
            logger.debug(f"[i] Already in autostart (Linux): {desktop_file}")
            return

        autostart_dir.mkdir(parents=True, exist_ok=True)
        content = f"""[Desktop Entry]
Type=Application
Exec={command}
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Name={app_name}
"""
        desktop_file.write_text(content)
        logger.debug(f"[✓] Added to autostart (Linux): {desktop_file}")

    elif system == "Darwin":
        plist_path = Path.home() / "Library" / "LaunchAgents" / f"{app_name}.plist"

        if plist_path.exists():
            logger.debug(f"[i] Already in autostart (macOS): {plist_path}")
            return

        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{app_name}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_exe}</string>
        <string>{script_path}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
"""
        plist_path.parent.mkdir(parents=True, exist_ok=True)
        plist_path.write_text(plist_content)
        os.system(f"launchctl load {plist_path}")
        logger.debug(f"[✓] Added to autostart (macOS): {plist_path}")

    else:
        raise NotImplementedError(f"Autostart is not supported for OS: {system}")
    
    
def disable_autostart(app_name: str):
    """
    Removes the Python script from autostart by application name.

    :param app_name: Application name (used as the shortcut/file/plist name)
    """
    system = platform.system()

    if system == "Windows":
        startup_dir = os.path.join(os.getenv('APPDATA'), r'Microsoft\Windows\Start Menu\Programs\Startup')
        shortcut_path = os.path.join(startup_dir, f"{app_name}.lnk")
        if os.path.exists(shortcut_path):
            os.remove(shortcut_path)
            logger.debug(f"[✓] Removed from autostart (Windows): {shortcut_path}")
        else:
            logger.debug(f"[i] Autostart not found (Windows)")

    elif system == "Linux":
        desktop_file = Path.home() / ".config" / "autostart" / f"{app_name}.desktop"
        if desktop_file.exists():
            desktop_file.unlink()
            logger.debug(f"[✓] Removed from autostart (Linux): {desktop_file}")
        else:
            logger.debug(f"[i] Autostart not found (Linux)")

    elif system == "Darwin":
        plist_path = Path.home() / "Library" / "LaunchAgents" / f"{app_name}.plist"
        if plist_path.exists():
            os.system(f"launchctl unload {plist_path}")
            plist_path.unlink()
            logger.debug(f"[✓] Removed from autostart (macOS): {plist_path}")
        else:
            logger.debug(f"[i] Autostart not found (macOS)")

    else:
        raise NotImplementedError(f"OS not supported: {system}")


if __name__ == "__main__":
    # enable_autostart(APP_NAME, get_project_main_path())
    disable_autostart(APP_NAME)
