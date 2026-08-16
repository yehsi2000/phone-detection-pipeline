import os
import sys
import time
from src.user.user_app import ApplicationController

def get_resource_path(relative_path):
    """Returns the absolute path to the resource."""
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), relative_path))

def main():
    try:
        # app = ApplicationController(model_path=get_resource_path("models/model.pt"))
        app = ApplicationController(model_path=get_resource_path("models/model.onnx"))
        app.start()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        app.stop()

if __name__ == "__main__":
    main()
