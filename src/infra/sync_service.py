import os
import time
import json
import uuid
import logging
import platform
import getpass
import threading
import sqlite3
import requests
from typing import Optional, Dict, Any

logger = logging.getLogger("SyncService")


class SyncService:
    """
    Background worker that syncs client telemetry & detection events to the Central Server.
    Provides offline resilience: pending events are queued locally and retried when network restores.
    """

    def __init__(self, server_url: str, client_id: str, db_path: str = "logs/detection_log.db", sync_interval: int = 5):
        self.server_url = server_url.rstrip("/")
        self.client_id = client_id or str(uuid.uuid4())[:8]
        self.db_path = db_path
        self.sync_interval = sync_interval

        self._stopped = threading.Event()
        self._sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
        self._init_local_sync_table()
        self.is_online = False

    def _init_local_sync_table(self):
        """Creates table for tracking sync status of logs if needed."""
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS pending_sync (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT,
                        event TEXT,
                        frame_path TEXT,
                        screen_path TEXT,
                        confidence TEXT,
                        active_apps TEXT,
                        username TEXT,
                        device TEXT,
                        bbox TEXT,
                        status TEXT DEFAULT 'PENDING'
                    )
                """)
                conn.commit()
        except Exception as e:
            logger.warning(f"Error initializing pending_sync table: {e}")

    def start(self):
        """Starts the background sync loop."""
        self._stopped.clear()
        self._sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
        self._sync_thread.start()
        logger.info(f"SyncService started for server {self.server_url} (client_id={self.client_id})")

    def stop(self):
        """Stops the sync service."""
        self._stopped.set()
        if self._sync_thread.is_alive():
            self._sync_thread.join(timeout=2.0)

    def enqueue_event(
        self,
        event: str,
        timestamp: str,
        frame_path: Optional[str] = None,
        screen_path: Optional[str] = None,
        confidence: Optional[list] = None,
        active_apps: Optional[list] = None,
        username: Optional[str] = None,
        device: Optional[str] = None,
        bbox: Optional[list] = None,
    ):
        """Enqueues an event for syncing to the central server."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO pending_sync 
                    (timestamp, event, frame_path, screen_path, confidence, active_apps, username, device, bbox, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING')
                    """,
                    (
                        timestamp,
                        event,
                        frame_path,
                        screen_path,
                        json.dumps(confidence) if confidence else None,
                        json.dumps(active_apps) if active_apps else None,
                        username or getpass.getuser(),
                        device or platform.node(),
                        json.dumps(bbox) if bbox else None,
                    ),
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to enqueue event for sync: {e}")

    def send_heartbeat(self):
        """Registers/updates client device state on the central server."""
        try:
            payload = {
                "client_id": self.client_id,
                "hostname": platform.node(),
                "username": getpass.getuser(),
                "os_info": f"{platform.system()} {platform.release()}",
                "status": "ONLINE",
            }
            resp = requests.post(f"{self.server_url}/api/telemetry/register", json=payload, timeout=4.0)
            if resp.status_code in (200, 201):
                self.is_online = True
                return True
        except Exception as e:
            self.is_online = False
            logger.debug(f"Heartbeat failed (server unreachable): {e}")
        return False

    def _sync_pending_events(self):
        """Flushes pending local events to the server."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, timestamp, event, frame_path, screen_path, confidence, active_apps, username, device, bbox FROM pending_sync WHERE status = 'PENDING' ORDER BY id ASC LIMIT 10")
                rows = cursor.fetchall()

            for row in rows:
                row_id, timestamp, event, frame_path, screen_path, conf_json, apps_json, username, device, bbox_json = row
                
                # Prepare multipart files
                files = {}
                opened_files = []
                try:
                    if frame_path and os.path.exists(frame_path):
                        f1 = open(frame_path, "rb")
                        opened_files.append(f1)
                        files["frame_file"] = (os.path.basename(frame_path), f1, "image/jpeg")
                    if screen_path and os.path.exists(screen_path):
                        f2 = open(screen_path, "rb")
                        opened_files.append(f2)
                        files["screen_file"] = (os.path.basename(screen_path), f2, "image/jpeg")

                    data = {
                        "client_id": self.client_id,
                        "timestamp": timestamp,
                        "event": event,
                        "confidence": conf_json or "[]",
                        "active_apps": apps_json or "[]",
                        "username": username or "",
                        "device": device or "",
                        "bbox": bbox_json or "[]",
                    }

                    resp = requests.post(f"{self.server_url}/api/telemetry/events", data=data, files=files, timeout=10.0)
                    if resp.status_code in (200, 201):
                        with sqlite3.connect(self.db_path) as conn:
                            cursor = conn.cursor()
                            cursor.execute("DELETE FROM pending_sync WHERE id = ?", (row_id,))
                            conn.commit()
                        logger.debug(f"Successfully synced event {row_id} to central server")
                    else:
                        logger.warning(f"Server returned {resp.status_code} on event sync: {resp.text}")
                        break
                finally:
                    for f in opened_files:
                        f.close()

        except Exception as e:
            logger.debug(f"Sync pending events error: {e}")

    def _sync_loop(self):
        """Worker loop for heartbeat and event dispatch."""
        last_heartbeat = 0
        while not self._stopped.is_set():
            now = time.time()
            # Send heartbeat every 30s
            if now - last_heartbeat > 30:
                self.send_heartbeat()
                last_heartbeat = now

            if self.is_online:
                self._sync_pending_events()

            time.sleep(self.sync_interval)
