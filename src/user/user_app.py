import os
import sys
import cv2
import numpy as np
import logging
import time
import threading
import platform
import getpass
import signal
from datetime import datetime
from typing import Optional
from skimage.metrics import structural_similarity as ssim

os.environ["OPENCV_VIDEOIO_DEBUG"] = "0"
os.environ["OPENCV_LOG_LEVEL"] = "OFF"
cv2.setLogLevel(0)

from src.core.detector import Detector
from src.core.lock_screen import lock_screen, is_screen_locked, wait_for_unlock
from src.core.logger import Logger
from src.core.config import Config
from src.core.system_info import get_active_apps
from src.infra.take_screenshot import take_screenshot
from src.infra.minimize_all import minimize_all_windows
from src.infra.set_admin_only_acess import set_admin_only_access
from src.infra.sync_service import SyncService
from src.infra.model_updater import ModelUpdater
from src.infra.is_admin import is_admin
from src.infra.critical_error import critical_error

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s:%(message)s')
logger = logging.getLogger("UserApp")


def get_resource_path(relative_path):
    """Returns absolute path to resource."""
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', relative_path))


class CameraStream:
    """
    Thread-safe video capture from a single camera with pause, warmup, and graceful shutdown support.
    """

    def __init__(
        self,
        source: int | str = 0,
        warmup_seconds: int = 2,
        max_fps: int = 2,
    ) -> None:
        self.source = source
        self.warmup_seconds = warmup_seconds
        self.max_fps = max_fps

        self._cap: Optional[cv2.VideoCapture] = None
        self._latest_frame: Optional["cv2.typing.MatLike"] = None
        self._new_frame_ready = threading.Event()
        self._last_frame_time = 0.0

        self._paused = threading.Event()
        self._stopped = threading.Event()
        self._ready = threading.Event()
        self._camera_lost = threading.Event()
        self._error_event = threading.Event()

        self._thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._lock = threading.Lock()

    def _open_camera(self):
        backends = [
            ("MSMF", cv2.CAP_MSMF),
            ("DSHOW", cv2.CAP_DSHOW),
        ]
        for name, backend in backends:
            cap = cv2.VideoCapture(self.source, backend)
            if cap.isOpened():
                logger.debug(f"DEBUG: Camera opened with {name}")
                return cap
            cap.release()
        return cv2.VideoCapture(self.source)

    def start(self) -> None:
        self._cap = self._open_camera()
        if not self._cap.isOpened():
            self._camera_lost.set()
            self._error_event.set()
            return

        self._paused.clear()
        self._stopped.clear()
        self._ready.clear()
        self._camera_lost.clear()
        self._error_event.clear()

        self._thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._thread.start()

    def is_camera_lost(self) -> bool:
        return self._camera_lost.is_set()

    def _reader_loop(self) -> None:
        failure_count = 0
        max_failures = 10
        first_frame_read = False

        while not self._stopped.is_set():
            if self._paused.is_set():
                time.sleep(0.05)
                continue

            ret, frame = self._cap.read()
            if not ret:
                failure_count += 1
                if failure_count >= max_failures:
                    self._camera_lost.set()
                    self._error_event.set()
                    break
                time.sleep(0.1)
                continue

            if not first_frame_read:
                first_frame_read = True
                time.sleep(self.warmup_seconds)
                self._ready.set()

            failure_count = 0

            with self._lock:
                self._latest_frame = frame
                self._new_frame_ready.set()

    def get_frame(self, timeout: float = 1.0) -> Optional["cv2.typing.MatLike"]:
        if not self._ready.is_set():
            return None

        is_new = self._new_frame_ready.wait(timeout=timeout)
        if not is_new:
            return None

        now = time.monotonic()
        delay = 1.0 / self.max_fps
        if now - self._last_frame_time < delay:
            return None

        with self._lock:
            frame = self._latest_frame.copy() if self._latest_frame is not None else None
            self._new_frame_ready.clear()
            self._last_frame_time = now
            return frame

    def pause(self) -> None:
        self._paused.set()

    def resume(self) -> None:
        self._paused.clear()

    def stop(self) -> None:
        self._stopped.set()
        self._thread.join(timeout=2)
        if self._cap is not None:
            self._cap.release()

    def is_ready(self) -> bool:
        return self._ready.is_set()


class ApplicationController:
    """
    Client detection agent managing video capture, local YOLO inference, local locking,
    and asynchronous syncing to the Central Server.
    """

    def __init__(self, model_path: str) -> None:
        if not is_admin():
            critical_error(logger)

        self.config = Config()
        self.logger = Logger()
        self.model_path = model_path

        self.phone_limit = self.config.get("phone_limit")
        self.fps = self.config.get("fps")
        self.camera_id = self.config.get("camera_id")
        self.confidence_threshold = self.config.get("confidence_threshold")
        self.min_step_time = 0.5 / max(1, self.fps)

        server_url = self.config.get("server_url")
        client_id = self.config.get("client_id")

        print(f"[Client Agent] Config: server_url={server_url}, camera_id={self.camera_id}, fps={self.fps}, conf={self.confidence_threshold}")

        # Core Detector
        self.detector = Detector(model_path=self.model_path)

        # Sync Service & Model Updater
        self.sync_service = SyncService(
            server_url=server_url,
            client_id=client_id,
            sync_interval=self.config.get("sync_interval_seconds") or 5
        )
        self.model_updater = ModelUpdater(
            server_url=server_url,
            current_model_path=self.model_path,
            detector=self.detector,
            check_interval=self.config.get("model_check_interval_seconds") or 60
        )

        self.camera = CameraStream(
            source=self.camera_id,
            warmup_seconds=2,
            max_fps=self.fps,
        )

        set_admin_only_access("logs")
        self._loop_thread = threading.Thread(target=self._main_loop, daemon=True)
        self._stop_event = threading.Event()
        self.start_time = time.perf_counter()

        signal.signal(signal.SIGTERM, self.handle_termination)
        signal.signal(signal.SIGINT, self.handle_termination)

    def handle_termination(self, signum, frame):
        logger.info("Termination signal detected")
        active_apps = get_active_apps()
        cam_frame = self.camera.get_frame(timeout=1.0) if (self.camera._cap and self.camera._cap.isOpened()) else None
        if self.config.get("log_events").get("attempt_to_close", True):
            self.prepare_logging("Attempt to close application", cam_frame, log_enable=True, lock_enable=False)
        if self.config.get("lock_events").get("attempt_to_close", False):
            lock_screen()

        self.camera.stop()
        self.sync_service.stop()
        self.model_updater.stop()
        cv2.destroyAllWindows()
        sys.exit(0)

    def prepare_logging(
        self,
        event: str,
        frame: Optional[np.ndarray],
        log_enable: bool = True,
        lock_enable: bool = False,
        bbox: Optional[list] = None,
        confs: Optional[list] = None,
    ) -> None:
        logger.info(f"Event triggered: {event}")
        active_apps = get_active_apps()
        username = str(getpass.getuser())
        pc_name = str(platform.node())
        screen = take_screenshot()
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        # Draw bbox copy on frame for display/logging if present
        log_frame = frame.copy() if frame is not None else None
        if log_frame is not None and bbox is not None and event == "Mobile phone detected":
            x1, y1, x2, y2 = bbox
            cv2.rectangle(log_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(log_frame, f"Phone {confs[0]:.2f}" if confs else "Phone", (x1, max(15, y1 - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        # 1. Local Logging
        if log_enable:
            self.logger.log_event(event, log_frame, screen, username, timestamp, confs, active_apps=active_apps, device=pc_name)

            # 2. Asynchronous Sync to Central Server
            event_slug = self.logger.event_slugs.get(event, event.lower().replace(" ", "_"))
            frame_path = self.logger._get_log_file_path(f"logs/{timestamp}_{event_slug}.jpg") if frame is not None else None
            screen_path = self.logger._get_log_file_path(f"logs/{timestamp}_{event_slug}_screen.jpg") if screen is not None else None

            self.sync_service.enqueue_event(
                event=event,
                timestamp=timestamp,
                frame_path=frame_path,
                screen_path=screen_path,
                confidence=confs,
                active_apps=active_apps,
                username=username,
                device=pc_name,
                bbox=bbox,
            )

        # 3. Local Lock Action
        if lock_enable:
            try:
                minimize_all_windows()
            except Exception as e:
                logger.warning(f"Error minimizing windows: {e}")
            lock_screen()
            for _ in range(20):
                if is_screen_locked():
                    break
                time.sleep(0.2)

    def start(self) -> None:
        logger.info("[Client Agent] Starting camera, sync services, and detection loop...")
        self.camera.start()
        self.sync_service.start()
        self.model_updater.start()

        if self.camera.is_camera_lost():
            logger.warning("[Client Agent] Camera unavailable at startup")
            self.prepare_logging(
                "Camera not connected at startup",
                frame=None,
                log_enable=self.config.get("log_events").get("camera_lost", True),
                lock_enable=self.config.get("lock_events").get("camera_lost", False),
            )

        self._loop_thread.start()

    def stop(self) -> None:
        logger.info("[Client Agent] Stopping application...")
        self._stop_event.set()
        self.camera.stop()
        self.sync_service.stop()
        self.model_updater.stop()

    def sleep_remain(self, step_start) -> None:
        elapsed = time.perf_counter() - step_start
        remaining = self.min_step_time - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def _main_loop(self) -> None:
        status_continued = {
            "uniform_image": False,
            "static_img": False,
            "camera_lost": False,
        }
        phone_count: int = 0
        last_frame = None
        last_unique_frame_time = time.time()

        while not self._stop_event.is_set():
            step_start = time.perf_counter()

            if is_screen_locked():
                self.camera.pause()
                wait_for_unlock()
                self.camera.resume()

            if self.camera.is_camera_lost():
                if not status_continued["camera_lost"]:
                    self.prepare_logging(
                        "Camera connection lost",
                        frame=None,
                        log_enable=self.config.get("log_events").get("camera_lost", True),
                        lock_enable=self.config.get("lock_events").get("camera_lost", False),
                    )
                    status_continued["camera_lost"] = True
                self.sleep_remain(step_start)
                break

            frame = self.camera.get_frame(timeout=1.0)
            self.start_time = time.perf_counter()
            if frame is None:
                self.sleep_remain(step_start)
                continue

            if is_uniform(frame):
                if not status_continued["uniform_image"]:
                    self.prepare_logging(
                        "Monochromatic image",
                        frame,
                        log_enable=self.config.get("log_events").get("uniform_image", True),
                        lock_enable=self.config.get("lock_events").get("uniform_image", False),
                    )
                    status_continued["uniform_image"] = True
                    self.sleep_remain(step_start)
                    continue
            elif status_continued["uniform_image"]:
                self.prepare_logging(
                    "After monochromatic image",
                    frame,
                    log_enable=self.config.get("log_events").get("uniform_image", True),
                    lock_enable=False,
                )
                status_continued["uniform_image"] = False

            now = time.time()
            if last_frame is not None and is_similar_frame(frame, last_frame):
                if not status_continued["static_img"]:
                    if now - last_unique_frame_time > 30:
                        self.prepare_logging(
                            "Frozen image",
                            frame,
                            log_enable=self.config.get("log_events").get("static_img", True),
                            lock_enable=self.config.get("lock_events").get("static_img", False),
                        )
                        status_continued["static_img"] = True
                        self.sleep_remain(step_start)
                        continue
            else:
                last_unique_frame_time = now
                last_frame = frame.copy()
                if status_continued["static_img"]:
                    self.prepare_logging(
                        "Image unfrozen",
                        frame,
                        log_enable=self.config.get("log_events").get("static_img", True),
                        lock_enable=False,
                    )
                    status_continued["static_img"] = False

            # Local YOLO Inference
            found, bbox, confs = self.detector.detect_phone(
                frame,
                conf=self.confidence_threshold
            )
            if found:
                phone_count += 1
                if phone_count >= self.phone_limit:
                    logger.info(f"[Client Agent] Phone detected: bbox={bbox}, conf={confs[0]:.2f}")
                    self.prepare_logging(
                        "Mobile phone detected",
                        frame,
                        log_enable=self.config.get("log_events").get("phone_detected", True),
                        lock_enable=self.config.get("lock_events").get("phone_detected", False),
                        bbox=bbox,
                        confs=confs,
                    )
                    self.sleep_remain(step_start)
                    continue
            else:
                phone_count = 0

            self.sleep_remain(step_start)


def is_uniform(frame):
    try:
        if frame is None:
            return False
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        variance = cv2.meanStdDev(gray)[1][0][0]
        return variance < 10
    except Exception as e:
        logger.warning(f"Uniformity check error: {e}")
        return False


def is_similar_frame(frame1: np.ndarray, frame2: np.ndarray,
                     ssim_threshold: float = 0.95,
                     mean_diff_threshold: float = 5.0) -> bool:
    if frame1.shape != frame2.shape:
        return False
    gray1 = cv2.GaussianBlur(cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    gray2 = cv2.GaussianBlur(cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    similarity, _ = ssim(gray1, gray2, full=True)
    mean_diff = np.mean(cv2.absdiff(gray1, gray2))
    return similarity >= ssim_threshold and mean_diff <= mean_diff_threshold


if __name__ == "__main__":
    try:
        app = ApplicationController(model_path="models/model.onnx")
        app.start()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        app.stop()
