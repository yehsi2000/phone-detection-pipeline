import os
import sys
import ctypes


def get_run_path():
    # Get path to the main executable file or script
    if getattr(sys, 'frozen', False):  # If packaged by PyInstaller
        return os.path.abspath(sys.executable)
    # If run as a Python script
    # sys.argv[0] points to the main script launched from the console
    return os.path.abspath(sys.argv[0])


def is_admin():
    try:
        # For Windows
        if os.name == 'nt':
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        # For Linux/macOS
        else:
            return os.geteuid() == 0
    except AttributeError:
        # If os.geteuid() is unavailable (e.g. on Windows)
        return False