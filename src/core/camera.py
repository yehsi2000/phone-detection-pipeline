import cv2
import os
import logging

cv2.setLogLevel(0)
os.environ["OPENCV_VIDEOIO_DEBUG"] = "0"
os.environ["OPENCV_LOG_LEVEL"] = "OFF"

logging.basicConfig(level=logging.CRITICAL+1, format='%(asctime)s %(levelname)s:%(message)s')
logger = logging.getLogger(__name__)

class Camera:
    def __init__(self, device_id=0):
        self.device_id = device_id
        try:
            self.cap = self._open_camera(device_id)
            if not self.cap.isOpened():
                raise Exception(f"Failed to open camera with ID {device_id}")
            logger.debug(f"DEBUG: Camera {device_id} opened")
        except Exception as e:
            logger.debug(f"DEBUG: Camera {device_id} initialization error: {e}")
            raise

    @staticmethod
    def _open_camera(device_id):
        backends = [
            ("MSMF", cv2.CAP_MSMF),
            ("DSHOW", cv2.CAP_DSHOW),
        ]
        for name, backend in backends:
            cap = cv2.VideoCapture(device_id, backend)
            if cap.isOpened():
                logger.debug(f"DEBUG: Camera opened with {name}")
                return cap
            cap.release()
        return cv2.VideoCapture(device_id)

    def get_frame(self):
        try:
            ret, frame = self.cap.read()
            if not ret:
                logger.debug(f"DEBUG: Failed to get frame from camera {self.device_id}")
                return None
            return frame
        except Exception as e:
            logger.debug(f"DEBUG: Frame capture error: {e}")
            return None

    def is_uniform(self, frame):
        try:
            if frame is None:
                return False
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            variance = cv2.meanStdDev(gray)[1][0][0]
            is_uniform = variance < 10
            logger.debug(f"DEBUG: Uniformity check: variance={variance}, is_uniform={is_uniform}")
            return is_uniform
        except Exception as e:
            logger.debug(f"DEBUG: Uniformity check error: {e}")
            return False

    def release(self):
        try:
            if hasattr(self, 'cap') and self.cap is not None:
                self.cap.release()
                logger.debug(f"DEBUG: Camera {self.device_id} released")
        except Exception as e:
            logger.debug(f"DEBUG: Camera release error: {e}")

    @staticmethod
    def list_available_cameras():
        cv2.setLogLevel(0)
        cameras = []
        max_index = 10
        for i in range(max_index):
            cap = None
            backend_used = "DEFAULT"
            try:
                cap = cv2.VideoCapture(i)
                if cap is None or not cap.isOpened():
                    continue
                ret, frame = cap.read()
                if not ret or frame is None:
                    continue
                cameras.append((i, f"Camera {i}"))
                logger.debug(f"DEBUG: Found camera: ID={i}, backend={backend_used}")
            except Exception as e:
                logger.debug(f"DEBUG: Camera {i} error: {e}")
            finally:
                if cap is not None:
                    cap.release()
        return cameras