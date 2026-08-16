import json
import os
import sys
import uuid
import logging

from src.infra.set_admin_only_acess import set_admin_only_access

# Logging configuration
logging.basicConfig(level=logging.CRITICAL+1, format='%(asctime)s %(levelname)s:%(message)s')
logger = logging.getLogger(__name__)

class Config:
    def __init__(self):
        self.default_config = {
            "camera_id": 0,
            "fps": 2,
            "log_retention": "1 month",
            "confidence_threshold": 0.6,
            "phone_limit": 1,
            "server_url": "http://localhost:8000",
            "client_id": str(uuid.uuid4())[:8],
            "sync_interval_seconds": 5,
            "model_check_interval_seconds": 60,
            "lock_events": {
                "camera_lost": True,
                "uniform_image": True,
                "phone_detected": True,
                "attempt_to_close": False,
                "static_img": True
            },
            "log_events": {
                "phone_detected": True,
                "camera_lost": True,
                "uniform_image": True,
                "attempt_to_close": True,
                "static_img": True
            },
            "other_events": {
                "make_screen_enabled": True
            },
            "autostart": {
                "on_system_start": False,
                "on_program_start": {"enabled": False, "program_path": ""},
                "on_file_open": {"enabled": False, "file_path": ""}
            }
        }
        self.config_path = self._get_config_path()
        self.config = self.load_config()
        logger.debug(f"Initialized Config with config_path: {self.config_path}")

    def _get_base_path(self):
        """Returns base path: sys._MEIPASS for .exe or project root."""
        if getattr(sys, 'frozen', False):
            return sys._MEIPASS
        return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

    def _get_writeable_path(self):
        """Returns writeable path (next to .exe or project root)."""
        if getattr(sys, 'frozen', False):
            return os.path.dirname(os.path.abspath(sys.executable))
        return self._get_base_path()

    def _get_config_path(self):
        """Returns path for reading config.json."""
        base_path = self._get_base_path()
        return os.path.join(base_path, 'config.json')

    def load_config(self):
        """Loads config.json."""
        try:
            writeable_path = os.path.join(self._get_writeable_path(), 'config.json')
            if os.path.exists(writeable_path):
                with open(writeable_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)

            # Update missing keys from default_config
            modified = False
            for key, value in self.default_config.items():
                if key not in config:
                    config[key] = value
                    modified = True
            
            # Clean up deprecated telegram keys if present
            if "telegram_ids" in config:
                del config["telegram_ids"]
                modified = True
            if "notifications_enabled" in config:
                del config["notifications_enabled"]
                modified = True
            if "notifications" in config:
                del config["notifications"]
                modified = True

            if modified:
                self.save_config(config)
            return config
        except FileNotFoundError:
            logger.warning(f"Config file not found at {self.config_path}, using defaults")
            cfg = self.default_config.copy()
            self.save_config(cfg)
            return cfg
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return self.default_config.copy()

    def save_config(self, config):
        """Saves config.json to writeable directory."""
        try:
            writeable_path = os.path.join(self._get_writeable_path(), 'config.json')
            with open(writeable_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
            self.config = config
            self.config_path = writeable_path
            set_admin_only_access(writeable_path)
        except Exception as e:
            logger.error(f"Error saving config to {writeable_path}: {e}")

    def get(self, key):
        """Gets value by key, returns default_config value if missing."""
        return self.config.get(key, self.default_config.get(key))