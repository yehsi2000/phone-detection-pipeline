# import platform
# import numpy as np
# import cv2

# def take_screenshot() -> np.ndarray:
#     """
#     Takes a screenshot of the screen and returns it as a NumPy array (BGR).
#     """
#     system = platform.system()

#     if system == "Windows":
#         try:
#             import win32gui
#             import win32ui
#             import win32con
#             import win32api

#             hdesktop = win32gui.GetDesktopWindow()
#             width = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
#             height = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
#             left = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
#             top = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)

#             desktop_dc = win32gui.GetWindowDC(hdesktop)
#             img_dc = win32ui.CreateDCFromHandle(desktop_dc)
#             mem_dc = img_dc.CreateCompatibleDC()

#             screenshot = win32ui.CreateBitmap()
#             screenshot.CreateCompatibleBitmap(img_dc, width, height)
#             mem_dc.SelectObject(screenshot)

#             # Try BitBlt
#             success = mem_dc.BitBlt((0, 0), (width, height), img_dc, (left, top), win32con.SRCCOPY)
#             if not success:
#                 raise RuntimeError("BitBlt failed")

#             bmpinfo = screenshot.GetInfo()
#             bmpstr = screenshot.GetBitmapBits(True)
#             img = np.frombuffer(bmpstr, dtype=np.uint8).reshape(
#                 (bmpinfo['bmHeight'], bmpinfo['bmWidth'], 4)
#             )

#             img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

#             # Free resources
#             mem_dc.DeleteDC()
#             win32gui.ReleaseDC(hdesktop, desktop_dc)
#             win32gui.DeleteObject(screenshot.GetHandle())

#             return img_bgr

#         except Exception as e:
#             print(f"WARNING: GDI screenshot failed, falling back to MSS. Reason: {e}")

#     # Linux, macOS or fallback
#     import mss
#     with mss.mss() as sct:
#         monitor = sct.monitors[0]
#         screenshot = sct.grab(monitor)
#         img = np.array(screenshot)  # BGRA
#         img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
#         return img_bgr



from pathlib import Path
import mss
import numpy as np
import cv2
import time
import sys
sys.path.append(r'D:\start_point\projects\phone_detection_app')
from src.core.lock_screen import lock_screen
import logging

logging.basicConfig(level=logging.CRITICAL+1, format='%(asctime)s %(levelname)s:%(message)s')
logger = logging.getLogger(__name__)


def take_screenshot() -> np.ndarray:
    """
    Takes a screenshot and saves it to the specified path.

    Cross-platform: works on Windows, Linux and macOS.

    :param save_path: Path to the file where the screenshot will be saved (e.g. 'output/screenshot.png')
    """
    with mss.mss() as sct:
        screenshot = sct.grab(sct.monitors[0])  # monitor[0] is the entire screen
        img = np.array(screenshot)  # BGRA format
        img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)  # remove alpha channel
        logger.debug('img_bgr')
    time.sleep(0.01)
    return np.array(img_bgr)


if __name__ == '__main__':
    save_path = Path('screen.jpg')
    save_path.parent.mkdir(parents=True, exist_ok=True)
    img = take_screenshot()
    cv2.imwrite(str(save_path), img)
    lock_screen()
