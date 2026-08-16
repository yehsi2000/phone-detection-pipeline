import ctypes
import time
import platform
import subprocess
from ctypes import wintypes
# from PyQt5.QtWidgets import QApplication
import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s:%(message)s')
logger = logging.getLogger(__name__)


def lock_screen() -> None:
    """
    Locks the screen.

    Cross-platform: works on Windows, Linux and macOS.
    """
    system = platform.system()
    logger.debug(f"DEBUG: Current system — {system}")

    if system == "Windows":
        logger.debug("DEBUG: Locking screen on Windows")
        ctypes.windll.user32.LockWorkStation()
    elif system == "Darwin":  # macOS
        logger.debug("DEBUG: Locking screen on macOS")
        subprocess.run([
            "/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession",
            "-suspend"
        ], check=False)
    elif system == "Linux":
        logger.debug("DEBUG: Locking screen on Linux")
        # Try several standard commands
        commands = [
            ["xdg-screensaver", "lock"],
            ["gnome-screensaver-command", "-l"],
            ["dm-tool", "lock"],
            ["loginctl", "lock-session"],
        ]
        for cmd in commands:
            try:
                subprocess.run(cmd, check=True)
                logger.debug(f"DEBUG: Successfully ran command: {' '.join(cmd)}")
                break
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
        else:
            logger.debug("ERROR: Failed to lock screen on Linux")
    else:
        raise NotImplementedError(f"Screen locking not supported for system: {system}")
    
    
# def is_screen_locked_windows() -> bool:
#     WTS_CURRENT_SERVER_HANDLE = ctypes.c_void_p(0)
#     WTS_CURRENT_SESSION = -1
#     WTSConnectStateClass = 0  # Enum: WTSConnectState

#     WTSActive = 0
#     WTSDisconnected = 4
#     WTSLocked = 8  # <-- this code may not work on all systems, depends on Windows version

#     wtsapi32 = ctypes.WinDLL('Wtsapi32.dll')
#     kernel32 = ctypes.WinDLL('kernel32.dll')

#     WTSQuerySessionInformationW = wtsapi32.WTSQuerySessionInformationW
#     WTSFreeMemory = wtsapi32.WTSFreeMemory

#     session_id = kernel32.WTSGetActiveConsoleSessionId()

#     buffer = ctypes.c_void_p()
#     bytes_returned = ctypes.wintypes.DWORD()

#     success = WTSQuerySessionInformationW(
#         WTS_CURRENT_SERVER_HANDLE,
#         session_id,
#         WTSConnectStateClass,
#         ctypes.byref(buffer),
#         ctypes.byref(bytes_returned)
#     )

#     if not success:
#         print("DEBUG: Failed to get session state")
#         return False

#     state = ctypes.cast(buffer, ctypes.POINTER(ctypes.wintypes.DWORD)).contents.value
#     WTSFreeMemory(buffer)

#     if state == WTSActive:
#         # print("DEBUG: Session active")
#         return False
#     else:
#         print(f"DEBUG: Session inactive, state: {state}")
#         return True


# def is_screen_locked_windows() -> bool:
#     # WTS constants
#     WTS_CURRENT_SERVER_HANDLE = ctypes.c_void_p(0)
#     WTS_CURRENT_SESSION = -1
#     WTS_CONNECTSTATE_CLASS = 4  # WTSConnectState

#     # Possible session states
#     WTSActive = 0
#     WTSConnected = 1
#     WTSConnectQuery = 2
#     WTSShadow = 3
#     WTSDisconnected = 4
#     WTSIdle = 5
#     WTSListen = 6
#     WTSReset = 7
#     WTSDown = 8
#     WTSInit = 9
#     # WTSLocked does not exist explicitly, but may relate to WTSDisconnected

#     # Load libraries
#     wtsapi32 = ctypes.WinDLL('wtsapi32.dll')
#     kernel32 = ctypes.WinDLL('kernel32.dll')

#     # Define function prototypes
#     WTSQuerySessionInformationW = wtsapi32.WTSQuerySessionInformationW
#     WTSQuerySessionInformationW.argtypes = [
#         wintypes.HANDLE,
#         wintypes.DWORD,
#         wintypes.DWORD,
#         ctypes.POINTER(ctypes.c_void_p),
#         ctypes.POINTER(wintypes.DWORD)
#     ]
#     WTSQuerySessionInformationW.restype = wintypes.BOOL

#     WTSFreeMemory = wtsapi32.WTSFreeMemory
#     WTSFreeMemory.argtypes = [ctypes.c_void_p]
#     WTSFreeMemory.restype = None

#     WTSGetActiveConsoleSessionId = kernel32.WTSGetActiveConsoleSessionId
#     WTSGetActiveConsoleSessionId.restype = wintypes.DWORD

#     # Get session ID
#     session_id = WTSGetActiveConsoleSessionId()
#     # print(f"DEBUG: Session ID: {session_id}")

#     buffer = ctypes.c_void_p()
#     bytes_returned = wintypes.DWORD()

#     # Query session state
#     success = WTSQuerySessionInformationW(
#         WTS_CURRENT_SERVER_HANDLE,
#         session_id,
#         WTS_CONNECTSTATE_CLASS,
#         ctypes.byref(buffer),
#         ctypes.byref(bytes_returned)
#     )

#     if not success:
#         error_code = ctypes.get_last_error()
#         print(f"DEBUG: Failed to get session state, error: {error_code}")
#         return False

#     # Get state value
#     state = ctypes.cast(buffer, ctypes.POINTER(wintypes.DWORD)).contents.value
#     WTSFreeMemory(buffer)

#     # Debug info
#     state_map = {
#         WTSActive: "WTSActive",
#         WTSConnected: "WTSConnected",
#         WTSConnectQuery: "WTSConnectQuery",
#         WTSShadow: "WTSShadow",
#         WTSDisconnected: "WTSDisconnected",
#         WTSIdle: "WTSIdle",
#         WTSListen: "WTSListen",
#         WTSReset: "WTSReset",
#         WTSDown: "WTSDown",
#         WTSInit: "WTSInit"
#     }
#     state_name = state_map.get(state, f"Unknown state: {state}")
#     if state != 1:
#         print(f"DEBUG: Session state: {state_name} ({state})")

#     # Check for locked screen
#     # Screen is considered locked if state is not WTSActive
#     return state != WTSActive


# def is_screen_locked_windows() -> bool:
#     user32 = ctypes.WinDLL('user32.dll')
#     OpenInputDesktop = user32.OpenInputDesktop
#     OpenInputDesktop.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
#     OpenInputDesktop.restype = wintypes.HDESK

#     CloseDesktop = user32.CloseDesktop
#     CloseDesktop.argtypes = [wintypes.HDESK]
#     CloseDesktop.restype = wintypes.BOOL

#     # Try to open current desktop
#     desktop = OpenInputDesktop(0, False, 0)
#     if not desktop:
#         print("DEBUG: Failed to open desktop")
#         return True  # Screen is likely locked

#     # Get desktop name
#     buffer = ctypes.create_unicode_buffer(256)
#     user32.GetUserObjectInformationW(
#         desktop, 2, buffer, 256, None  # 2 = UOI_NAME
#     )
#     desktop_name = buffer.value
#     CloseDesktop(desktop)

#     print(f"DEBUG: Desktop name: {desktop_name}")
#     # If desktop name is "Default", screen is not locked
#     return desktop_name != "Default"


# def is_screen_locked_windows() -> bool:
#     # WTS constants
#     WTS_CURRENT_SERVER_HANDLE = ctypes.c_void_p(0)
#     WTS_CONNECTSTATE_CLASS = 4  # WTSConnectState
#     WTS_SESSIONSTATE_CLASS = 24  # WTSSessionState (Windows 10/11)

#     # Possible session states
#     WTSActive = 0
#     WTSConnected = 1
#     WTSDisconnected = 4
#     WTSLocked = 8  # Not always used

#     # Load libraries
#     wtsapi32 = ctypes.WinDLL('wtsapi32.dll')
#     kernel32 = ctypes.WinDLL('kernel32.dll')

#     # Define function prototypes
#     WTSQuerySessionInformationW = wtsapi32.WTSQuerySessionInformationW
#     WTSQuerySessionInformationW.argtypes = [
#         wintypes.HANDLE,
#         wintypes.DWORD,
#         wintypes.DWORD,
#         ctypes.POINTER(ctypes.c_void_p),
#         ctypes.POINTER(wintypes.DWORD)
#     ]
#     WTSQuerySessionInformationW.restype = wintypes.BOOL

#     WTSFreeMemory = wtsapi32.WTSFreeMemory
#     WTSFreeMemory.argtypes = [ctypes.c_void_p]
#     WTSFreeMemory.restype = None

#     WTSGetActiveConsoleSessionId = kernel32.WTSGetActiveConsoleSessionId
#     WTSGetActiveConsoleSessionId.restype = wintypes.DWORD

#     # Get session ID
#     session_id = WTSGetActiveConsoleSessionId()
#     print(f"DEBUG: Session ID: {session_id}")

#     buffer = ctypes.c_void_p()
#     bytes_returned = wintypes.DWORD()

#     # Query connection state
#     success = WTSQuerySessionInformationW(
#         WTS_CURRENT_SERVER_HANDLE,
#         session_id,
#         WTS_CONNECTSTATE_CLASS,
#         ctypes.byref(buffer),
#         ctypes.byref(bytes_returned)
#     )

#     if not success:
#         error_code = ctypes.get_last_error()
#         print(f"DEBUG: Failed to get session state, error: {error_code}")
#         return False

#     state = ctypes.cast(buffer, ctypes.POINTER(wintypes.DWORD)).contents.value
#     WTSFreeMemory(buffer)

#     state_map = {
#         WTSActive: "WTSActive",
#         WTSConnected: "WTSConnected",
#         WTSDisconnected: "WTSDisconnected",
#         WTSLocked: "WTSLocked"
#     }
#     print(f"DEBUG: Session state: {state_map.get(state, f'Unknown state: {state}')} ({state})")

#     # Additional lock state check (Windows 10/11)
#     buffer = ctypes.c_void_p()
#     bytes_returned = wintypes.DWORD()

#     success = WTSQuerySessionInformationW(
#         WTS_CURRENT_SERVER_HANDLE,
#         session_id,
#         WTS_SESSIONSTATE_CLASS,  # Check lock state
#         ctypes.byref(buffer),
#         ctypes.byref(bytes_returned)
#     )

#     if success:
#         lock_state = ctypes.cast(buffer, ctypes.POINTER(wintypes.DWORD)).contents.value
#         WTSFreeMemory(buffer)
#         print(f"DEBUG: Lock state: {lock_state} (0=Active, 1=Locked, 2=Unlocked)")
#         return lock_state == 1  # 1 = SessionLocked
#     else:
#         error_code = ctypes.get_last_error()
#         print(f"DEBUG: Failed to get lock state, error: {error_code}")

#     # If WTSSessionState unavailable, use session state
#     return state == WTSDisconnected


# def is_screen_locked_windows() -> bool:
#     user32 = ctypes.WinDLL('user32.dll')
#     OpenInputDesktop = user32.OpenInputDesktop
#     OpenInputDesktop.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
#     OpenInputDesktop.restype = wintypes.HDESK

#     CloseDesktop = user32.CloseDesktop
#     CloseDesktop.argtypes = [wintypes.HDESK]
#     CloseDesktop.restype = wintypes.BOOL

#     desktop = OpenInputDesktop(0, False, 0)
#     if not desktop:
#         print("DEBUG: Failed to open desktop")
#         return True

#     buffer = ctypes.create_unicode_buffer(256)
#     user32.GetUserObjectInformationW(desktop, 2, buffer, 256, None)  # 2 = UOI_NAME
#     desktop_name = buffer.value
#     CloseDesktop(desktop)

#     print(f"DEBUG: Desktop name: {desktop_name}")
#     return desktop_name != "Default"

# wtsapi32 = ctypes.WinDLL('wtsapi32')

# class WTSINFOEX_LEVEL1(ctypes.Structure):
#     _fields_ = [
#         ("SessionId", wintypes.DWORD),
#         ("SessionState", wintypes.DWORD),
#         ("SessionFlags", wintypes.DWORD),
#     ]

# class WTSINFOEX(ctypes.Structure):
#     _fields_ = [
#         ("Level", wintypes.DWORD),
#         ("Data", WTSINFOEX_LEVEL1),
#     ]

# def is_screen_locked_windows():
#     WTS_CURRENT_SERVER_HANDLE = 0
#     WTS_CURRENT_SESSION = -1
#     WTSSessionInfoEx = 14

#     buffer = ctypes.c_void_p()
#     bytes_returned = wintypes.DWORD()

#     success = wtsapi32.WTSQuerySessionInformationW(
#         WTS_CURRENT_SERVER_HANDLE,
#         WTS_CURRENT_SESSION,
#         WTSSessionInfoEx,
#         ctypes.byref(buffer),
#         ctypes.byref(bytes_returned)
#     )

#     if not success:
#         error_code = ctypes.get_last_error()
#         print(f"Failed to query session info, error code: {error_code}")
#         return None

#     try:
#         info = ctypes.cast(buffer, ctypes.POINTER(WTSINFOEX)).contents
#         if info.Level != 1:
#             print(f"Unexpected level: {info.Level}")
#             return None

#         session_flags = info.Data.SessionFlags
#         if session_flags == 0:
#             return True  # Locked
#         elif session_flags == 1:
#             return False  # Unlocked
#         else:
#             print(f"Unknown session flag: {session_flags}")
#             return None
#     finally:
#         wtsapi32.WTSFreeMemory(buffer)


process_name='LogonUI.exe'
callall='TASKLIST'
# def is_screen_locked_windows():
#     outputall=subprocess.check_output(callall)
#     outputstringall=str(outputall)
#     if process_name in outputstringall:
#         logger.debug("Locked.")
#         return True
#     else: 
#         logger.debug("Unlocked.")
#         return False
def is_screen_locked_windows():
    try:
        # Use TASKLIST with CREATE_NO_WINDOW
        result = subprocess.run(
            ['tasklist'],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            shell=False,
            creationflags=0x08000000  # CREATE_NO_WINDOW
        )
        output = result.stdout
        if 'LogonUI.exe' in output:
            logger.debug("Locked.")
            return True
        logger.debug("Unlocked.")
        return False
    except Exception as e:
        logger.debug(f"Error checking screen lock: {e}")
        return False


def is_screen_locked() -> bool:
    """
    Checks if the screen is locked.

    Cross-platform: works on Windows, Linux and macOS.
    
    :return: True if screen is locked, else False
    """
    system = platform.system()
    # print(f"DEBUG: Current system — {system}")
    if system == "Windows":
        try:
            return is_screen_locked_windows()

        except Exception as e:
            logger.debug(f"DEBUG: Screen lock check error on Windows: {e}")
            return False
    elif system == "Darwin":
        try:
            output = subprocess.run(
                ["/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession", "-s"],
                capture_output=True,
                text=True
            ).stdout

            if "Locked = 1" in output:
                logger.debug("DEBUG: Screen locked (macOS: CGSession reports Locked=1)")
                return True
            else:
                logger.debug("DEBUG: Screen unlocked (macOS)")
                return False
        except Exception as e:
            logger.debug(f"DEBUG: Screen state check error on macOS: {e}")
            return False
    elif system == "Linux":
        try:
            import getpass

            user = getpass.getuser()
            session_list = subprocess.run(
                ["loginctl", "list-sessions", "--no-legend"],
                capture_output=True,
                text=True
            ).stdout

            for line in session_list.strip().splitlines():
                parts = line.split()
                if len(parts) >= 2 and parts[1] == user:
                    session_id = parts[0]
                    break
            else:
                logger.debug("DEBUG: Failed to find active user session")
                return False

            output = subprocess.run(
                ["loginctl", "show-session", session_id, "-p", "LockedHint"],
                capture_output=True,
                text=True
            ).stdout

            if "LockedHint=yes" in output:
                logger.debug("DEBUG: Screen locked (Linux: LockedHint=yes)")
                return True
            else:
                logger.debug("DEBUG: Screen unlocked (Linux)")
                return False

        except Exception as e:
            logger.debug(f"DEBUG: Screen state check error on Linux: {e}")
            return False

    # if system == "Windows":
    #     try:
    #         import win32gui

    #         # Check lock window
    #         hwnd = win32gui.FindWindow(None, "Windows Security")
    #         if hwnd != 0:
    #             print("DEBUG: Screen locked (found 'Windows Security' window)")
    #             return True

    #         # Alternative check: no active window
    #         foreground = win32gui.GetForegroundWindow()
    #         if foreground == 0:
    #             print("DEBUG: Screen locked (no active window)")
    #             return True

    #         # print("DEBUG: Screen unlocked")
    #         return False
    #     except Exception as e:
    #         print(f"DEBUG: Screen state check error on Windows: {e}")
    #         return False

    # elif system == "Darwin":  # macOS
    #     try:
    #         output = subprocess.run(
    #             ["ioreg", "-n", "IOHIDSystem"],
    #             capture_output=True,
    #             text=True
    #         ).stdout
    #         if "IOUserSessionLocked" in output and "Yes" in output:
    #             print("DEBUG: Screen locked (macOS: IOUserSessionLocked=Yes)")
    #             return True
    #         else:
    #             print("DEBUG: Screen unlocked (macOS)")
    #             return False
    #     except Exception as e:
    #         print(f"DEBUG: Screen state check error on macOS: {e}")
    #         return False

    # elif system == "Linux":
    #     try:
    #         # loginctl is used to check session status
    #         output = subprocess.run(
    #             ["loginctl", "show-session", str(get_current_session_id()), "-p", "LockedHint"],
    #             capture_output=True,
    #             text=True
    #         ).stdout
    #         if "LockedHint=yes" in output:
    #             print("DEBUG: Screen locked (Linux: LockedHint=yes)")
    #             return True
    #         else:
    #             print("DEBUG: Screen unlocked (Linux)")
    #             return False
    #     except Exception as e:
    #         print(f"DEBUG: Screen state check error on Linux: {e}")
    #         return False
    # else:
    #     raise NotImplementedError(f"Screen lock check not supported for system: {system}")


def get_current_session_id() -> int:
    """
    Returns the current user session ID in Linux (for loginctl).
    """
    try:
        output = subprocess.run(
            ["loginctl", "show-user", str(get_current_uid()), "-p", "Sessions"],
            capture_output=True,
            text=True
        ).stdout
        # Example response: "Sessions=2"
        session_line = output.strip()
        session_id = int(session_line.split("=")[-1])
        logger.debug(f"DEBUG: Found session ID: {session_id}")
        return session_id
    except Exception as e:
        logger.debug(f"DEBUG: Error getting session ID: {e}")
        raise RuntimeError("Failed to get current session ID")


def get_current_uid() -> int:
    """
    Returns the UID of the current user in Linux.
    """
    import os
    uid = os.getuid()
    logger.debug(f"DEBUG: Current UID: {uid}")
    return uid


# def wait_for_unlock():
#     """Wait for screen unlock"""
#     system = platform.system()

#     if system == "Windows":
#         import ctypes
#         from ctypes import wintypes

#         user32 = ctypes.WinDLL('user32', use_last_error=True)
#         WTS_CURRENT_SERVER_HANDLE = 0
#         WTS_SESSION_LOCK = 0x7
#         WTS_SESSION_UNLOCK = 0x8

#         def register_session_notification():
#             user32.WTSRegisterSessionNotification.restype = wintypes.BOOL
#             user32.WTSRegisterSessionNotification.argtypes = [wintypes.HWND, wintypes.DWORD]
#             return user32.WTSRegisterSessionNotification(0, 0)

#         if not register_session_notification():
#             print("Notification registration error")
#             return False

#         msg = wintypes.MSG()
#         while True:
#             if user32.GetMessageW(ctypes.byref(msg), 0, 0, 0):
#                 if msg.message == 0x02B1:  # WM_WTSSESSION_CHANGE
#                     if msg.wParam == WTS_SESSION_UNLOCK:
#                         print("Screen unlocked!")
#                         return True
#                     elif msg.wParam == WTS_SESSION_LOCK:
#                         print("Screen locked")
#             time.sleep(0.1)

#     elif system == "Linux":
#         try:
#             import dbus
#             from dbus.mainloop.glib import DBusGMainLoop
#             from gi.repository import GLib
#         except ImportError:
#             print("python-dbus and pygobject packages required")
#             return False

#         def screen_saver_handler(active):
#             if not active:
#                 print("Screen unlocked!")
#                 loop.quit()

#         DBusGMainLoop(set_as_default=True)
#         bus = dbus.SessionBus()
#         bus.add_signal_receiver(
#             screen_saver_handler,
#             signal_name="ActiveChanged",
#             dbus_interface="org.gnome.ScreenSaver"
#         )
#         loop = GLib.MainLoop()
#         loop.run()
#         return True

#     elif system == "Darwin":  # macOS
#         try:
#             from AppKit import NSWorkspace
#         except ImportError:
#             print("pyobjc-framework-Cocoa required")
#             return False

#         workspace = NSWorkspace.sharedWorkspace()
#         while True:
#             if not workspace.isScreenLocked():
#                 print("Screen unlocked!")
#                 return True
#             time.sleep(0.1)

#     else:
#         print(f"Operating system {system} not supported")
#         return False


def wait_for_unlock():
    """Wait for screen unlock"""
    logger.debug("DEBUG: Waiting for screen unlock")
    # app = QApplication.instance()
    while is_screen_locked():
        # if app:
        #     app.processEvents()  # Process PyQt5 events
        time.sleep(0.1)  # Check every second
    logger.debug("DEBUG: Screen unlocked, resuming analysis")


# def wait_for_unlock():
#     """Wait for screen unlock"""
#     print("DEBUG: Waiting for screen unlock")
#     while is_screen_locked():
#         time.sleep(0.1)  # Check every second
#     print("DEBUG: Screen unlocked, resuming analysis")
