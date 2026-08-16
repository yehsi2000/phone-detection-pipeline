import platform
import pyautogui
import time
import logging

logging.basicConfig(level=logging.CRITICAL+1, format='%(asctime)s %(levelname)s:%(message)s')
logger = logging.getLogger(__name__)

def minimize_all_windows():
    system = platform.system().lower()
    
    # Delay for safety
    pyautogui.PAUSE = 0.02
    
    if system == "windows":
        # Win + D to minimize all windows
        pyautogui.hotkey("win", "d")
        pyautogui.PAUSE = 0.02
        pyautogui.hotkey("win", "m")
    elif system == "darwin":  # macOS
        # Command + Option + M or F11 for macOS
        pyautogui.hotkey("command", "option", "m")
        # Alternative: pyautogui.hotkey("f11")
    elif system == "linux":
        # Ctrl + Alt + D for GNOME (may differ for other environments)
        pyautogui.hotkey("ctrl", "alt", "d")
    else:
        logger.warning("Operating system is not supported")

if __name__ == "__main__":
    # Give time to switch to the desired window
    print("Minimizing all windows in 2 seconds...")
    time.sleep(2)
    minimize_all_windows()