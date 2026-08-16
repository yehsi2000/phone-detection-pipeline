import os
import sys


def get_base_path():
    """Returns the base path: sys._MEIPASS for .exe or project root."""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

def get_resource_path(relative_path):
    """Returns the absolute path to a resource."""
    return os.path.join(get_base_path(), relative_path)


def get_image_path(relative_path):
    """
    Returns the absolute path to a resource, handling both .py and .exe execution.
    For .exe, uses the executable directory instead of sys._MEIPASS.
    """
    if getattr(sys, 'frozen', False):  # Running from .exe (PyInstaller)
        # Get the directory where the .exe is located
        base_path = os.path.dirname(sys.executable)
    else:  # Running from .py
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    return os.path.join(base_path, relative_path)
