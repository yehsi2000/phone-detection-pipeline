import os
import time
import hashlib
import logging
import threading
import requests
import onnxruntime as ort

logger = logging.getLogger("ModelUpdater")


class ModelUpdater:
    """
    Background worker that polls the central server for model updates and hot-reloads the Detector.
    """

    def __init__(self, server_url: str, current_model_path: str, detector, check_interval: int = 60):
        self.server_url = server_url.rstrip("/")
        self.current_model_path = current_model_path
        self.detector = detector
        self.check_interval = check_interval
        self._stopped = threading.Event()
        self._updater_thread = threading.Thread(target=self._update_loop, daemon=True)
        self.current_version = "v1.0.0"

    def start(self):
        self._stopped.clear()
        self._updater_thread = threading.Thread(target=self._update_loop, daemon=True)
        self._updater_thread.start()
        logger.info(f"ModelUpdater started (polling {self.server_url}/api/model/latest every {self.check_interval}s)")

    def stop(self):
        self._stopped.set()
        if self._updater_thread.is_alive():
            self._updater_thread.join(timeout=2.0)

    def _get_file_hash(self, file_path: str) -> str:
        """Calculates MD5 hash of local model file."""
        if not os.path.exists(file_path):
            return ""
        hasher = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def check_and_update(self) -> bool:
        """Checks if server has a newer model and updates local detector if available."""
        try:
            resp = requests.get(f"{self.server_url}/api/model/latest", timeout=5.0)
            if resp.status_code != 200:
                return False

            info = resp.json()
            server_version = info.get("version", "")
            server_hash = info.get("md5", "")

            local_hash = self._get_file_hash(self.current_model_path)
            if server_hash and server_hash == local_hash:
                return False  # Already up to date

            if not info.get("available", False):
                return False

            logger.info(f"New model available on server: {server_version} (Backbone: {info.get('backbone')})")

            # Download new model
            down_resp = requests.get(f"{self.server_url}/api/model/download", stream=True, timeout=30.0)
            if down_resp.status_code != 200:
                logger.warning(f"Failed to download new model: HTTP {down_resp.status_code}")
                return False

            os.makedirs(os.path.dirname(self.current_model_path), exist_ok=True)
            tmp_path = self.current_model_path + ".tmp"

            with open(tmp_path, "wb") as f:
                for chunk in down_resp.iter_content(chunk_size=65536):
                    f.write(chunk)

            # Validate ONNX runtime session on the downloaded file
            try:
                test_sess = ort.InferenceSession(tmp_path, providers=["CPUExecutionProvider"])
                del test_sess
            except Exception as e:
                logger.error(f"Downloaded model validation failed: {e}")
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                return False

            # Replace current model file
            if os.path.exists(self.current_model_path):
                backup_path = self.current_model_path + ".bak"
                try:
                    if os.path.exists(backup_path):
                        os.remove(backup_path)
                    os.rename(self.current_model_path, backup_path)
                except Exception as e:
                    logger.warning(f"Failed to create model backup: {e}")

            os.rename(tmp_path, self.current_model_path)
            self.current_version = server_version

            # Hot-reload detector
            success = self.detector.reload_model(self.current_model_path)
            if success:
                logger.info(f"Successfully updated and hot-reloaded model to {server_version}")
                return True
            else:
                logger.error("Hot-reload failed after model download")
                return False

        except Exception as e:
            logger.debug(f"Model update check failed: {e}")
            return False

    def _update_loop(self):
        while not self._stopped.is_set():
            self.check_and_update()
            time.sleep(self.check_interval)
