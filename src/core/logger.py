import sqlite3
import cv2
import os
import json
import sys
from datetime import datetime, timedelta
import queue
import threading
import logging

logging.basicConfig(level=logging.CRITICAL+1, format='%(asctime)s %(levelname)s:%(message)s')
logger = logging.getLogger("Logger")

class Logger:
    def __init__(self, db_path="logs/detection_log.db"):
        # Path setup
        self.db_path = db_path
        self.abs_db_path = self._get_db_path()
        os.makedirs(os.path.dirname(self.abs_db_path), exist_ok=True)
        logger.debug(f"Initializing logger with db_path={db_path}, absolute={self.abs_db_path}")

        # Dictionary to convert events to slug
        self.event_slugs = {
            "Mobile phone detected": "phone_detected",
            "Monochromatic image": "uniform_image",
            "After monochromatic image": "after_uniform_image",
            "Camera connection lost": "camera_lost",
            "Recovered from camera connection loss": "recovery_camera_lost",
            "Attempt to close application": "attempt_to_close",
            "Frozen image": "static_img",
            "Image unfrozen": "after_static_img",
        }

        try:
            if not os.path.exists(self.abs_db_path):
                logger.debug(f"Database {self.abs_db_path} does not exist, will be created")
            self.conn = sqlite3.connect(self.abs_db_path)
            self.cursor = self.conn.cursor()
            self._create_or_migrate_table()
            logger.debug(f"Connected to database {self.abs_db_path}")
        except sqlite3.OperationalError as e:
            logger.error(f"Error connecting to database {self.abs_db_path}: {e}")
            raise

        # Initialize queue and thread
        self.queue = queue.Queue(maxsize=100)  # Bounded queue
        self._stop_event = threading.Event()  # Event to stop thread
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()

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

    def _get_db_path(self):
        """Returns absolute path to database in writeable directory."""
        writeable_path = self._get_writeable_path()
        return os.path.join(writeable_path, self.db_path)

    def _get_log_file_path(self, relative_path):
        """Returns absolute path for log files (images)."""
        return os.path.join(self._get_writeable_path(), relative_path)

    def _create_or_migrate_table(self):
        """Create or migrate table in database."""
        try:
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    event TEXT,
                    frame_path TEXT,
                    screen_path TEXT,
                    confidence TEXT,
                    active_apps TEXT,
                    username TEXT,
                    device TEXT
                )
            """)
            self.cursor.execute("PRAGMA table_info(logs)")
            columns = [col[1] for col in self.cursor.fetchall()]
            logger.debug(f"Columns in logs table: {columns}")
            if "confidence" not in columns:
                self.cursor.execute("ALTER TABLE logs ADD COLUMN confidence TEXT")
                logger.debug("Added confidence column")
            if "active_apps" not in columns:
                self.cursor.execute("ALTER TABLE logs ADD COLUMN active_apps TEXT")
                logger.debug("Added active_apps column")
            if "username" not in columns:
                self.cursor.execute("ALTER TABLE logs ADD COLUMN username TEXT")
                logger.debug("Added username column")
            if "device" not in columns:
                self.cursor.execute("ALTER TABLE logs ADD COLUMN device TEXT")
                logger.debug("Added device column")
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Error creating/migrating table: {e}")
            raise

    def _worker_loop(self):
        """Logging task processing loop in a separate thread."""
        conn = sqlite3.connect(self.abs_db_path)
        cursor = conn.cursor()

        while not self._stop_event.is_set():
            try:
                task = self.queue.get(timeout=1.0)
                timestamp, event, frame_path, screen_path, username, confidence, active_apps, device = task

                confidence_json = json.dumps(confidence) if confidence is not None else None
                active_apps_json = json.dumps(active_apps) if active_apps is not None else None

                logger.debug(f"Logging event: event={event}, frame_path={frame_path}, screen_path={screen_path}, confidence={confidence_json}, active_apps={active_apps_json}, username={username}, device={device}")

                try:
                    cursor.execute(
                        "INSERT INTO logs (timestamp, event, frame_path, screen_path, confidence, active_apps, username, device) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (timestamp.replace("_", " "), event, frame_path, screen_path, confidence_json, active_apps_json, username, device)
                    )
                    conn.commit()
                    logger.debug(f"Event successfully logged to database: id={cursor.lastrowid}, username={username} on device={device}")
                except sqlite3.Error as e:
                    logger.warning(f"Error writing to database: {e}")

                self.queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in worker loop: {e}")

        cursor.close()
        conn.close()
        logger.debug("Logger worker thread stopped")

    def log_event(
        self, event, frame, screen, username,
        timestamp: str, confidence=None, active_apps=None,
        device: str = None):
        """
        Logging the event: saves images to disk and enqueues a task.
        """
        logger.debug(f"Logging event={event}")

        # Prepare event slug
        event_slug = self.event_slugs.get(event, event.lower().replace(" ", "_"))

        # Prepare image paths (always in writeable directory)
        frame_path = f"logs/{timestamp}_{event_slug}.jpg"
        abs_frame_path = self._get_log_file_path(frame_path)
        screen_path = f"logs/{timestamp}_{event_slug}_screen.jpg"
        abs_screen_path = self._get_log_file_path(screen_path)
        os.makedirs(os.path.dirname(abs_frame_path), exist_ok=True)

        # Save images
        if frame is not None:
            try:
                cv2.imwrite(abs_frame_path, frame)
                logger.debug(f"Saved frame: {abs_frame_path}")
            except Exception as e:
                logger.debug(f"Error saving frame {abs_frame_path}: {e}")
                frame_path = None
        else:
            logger.debug(f"Frame is None, skipping save for {abs_frame_path}")
            frame_path = None

        if screen is not None:
            try:
                cv2.imwrite(abs_screen_path, screen)
                logger.debug(f"Saved screen: {abs_screen_path}")
            except Exception as e:
                logger.debug(f"Error saving screen {abs_screen_path}: {e}")
                screen_path = None
        else:
            logger.debug(f"Screen is None, skipping save for {abs_screen_path}")
            screen_path = None

        # Put task in queue
        try:
            self.queue.put(
                (timestamp, event, frame_path, screen_path, username, confidence, active_apps, device),
                timeout=2.0
            )
        except queue.Full:
            logger.warning("Logging queue is full, dropping event")
            if frame_path and os.path.exists(abs_frame_path):
                try:
                    os.remove(abs_frame_path)
                    logger.debug(f"Deleted unsaved frame: {abs_frame_path}")
                except OSError as e:
                    logger.debug(f"Error deleting frame {abs_frame_path}: {e}")
            if screen_path and os.path.exists(abs_screen_path):
                try:
                    os.remove(abs_screen_path)
                    logger.debug(f"Deleted unsaved screen: {abs_screen_path}")
                except OSError as e:
                    logger.debug(f"Error deleting screen {abs_screen_path}: {e}")

    def get_logs(self):
        """Get all logs from database."""
        conn = sqlite3.connect(self.abs_db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM logs ORDER BY timestamp DESC")
            logs = cursor.fetchall()
            logger.debug(f"Loaded {len(logs)} logs from database")
            for log in logs:
                logger.debug(f"Log: id={log[0]}, timestamp={log[1]}, event={log[2]}, frame_path={log[3]}, screen_path={log[4]}, confidence={log[5]}, active_apps={log[6]}, username={log[7]}, device={log[8]}")
            return logs
        except sqlite3.Error as e:
            logger.error(f"Error reading logs from database: {e}")
            return []
        finally:
            cursor.close()
            conn.close()

    def clean_old_logs(self, retention_period):
        """Clean old logs and associated files."""
        if retention_period == "Never delete":
            return
        periods = {
            "1 day": timedelta(days=1),
            "1 week": timedelta(weeks=1),
            "1 month": timedelta(days=30),
            "1 year": timedelta(days=365)
        }
        if retention_period not in periods:
            return
        cutoff = datetime.now() - periods[retention_period]
        cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")

        conn = sqlite3.connect(self.abs_db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT frame_path, screen_path FROM logs WHERE timestamp < ?", (cutoff_str,))
            paths = cursor.fetchall()
            for frame_path, screen_path in paths:
                for path in (frame_path, screen_path):
                    if path:
                        abs_path = self._get_log_file_path(path)
                        try:
                            if os.path.exists(abs_path):
                                os.remove(abs_path)
                                logger.debug(f"Deleted old file: {abs_path}")
                        except OSError as e:
                            logger.debug(f"Error deleting file {abs_path}: {e}")
            cursor.execute("DELETE FROM logs WHERE timestamp < ?", (cutoff_str,))
            conn.commit()
            logger.debug(f"Deleted logs older than {cutoff_str}")
        except sqlite3.Error as e:
            logger.error(f"Error cleaning old logs: {e}")
        finally:
            cursor.close()
            conn.close()

    def close(self):
        """Stop processing thread and release resources."""
        logger.debug("Stopping Logger")
        self._stop_event.set()
        self._worker_thread.join(timeout=2.0)
        self.conn.close()
        logger.debug("Logger stopped")

    def __del__(self):
        """Guaranteed cleanup on object deletion."""
        self.close()


# import sqlite3
# import cv2
# import os
# import json
# from datetime import datetime, timedelta
# import queue
# import threading
# import logging

# logger = logging.getLogger("UserApp")

# class Logger:
#     def __init__(self, db_path):
#         # Use path relative to project root
#         base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
#         self.abs_db_path = os.path.join(base_dir, db_path)
#         os.makedirs(os.path.dirname(self.abs_db_path), exist_ok=True)
#         logger.debug(f"Initializing logger with db_path={db_path}, absolute={self.abs_db_path}")

#         # Dictionary to convert events to slug
#         self.event_slugs = {
#             "Mobile phone detected": "phone_detected",
#             "Monochromatic image": "uniform_image",
#             "After monochromatic image": "after_uniform_image",
#             "Camera connection lost": "camera_lost",
#             "Recovered from camera connection loss": "recovery_camera_lost",
#             "Attempt to close application": "attempt_to_close",
#             "Frozen image": "static_img",
#             "Image unfrozen": "after_static_img",
#         }
#         try:
#             if not os.path.exists(self.abs_db_path):
#                 print(f"DEBUG: Database {self.abs_db_path} does not exist, will be created")
#             self.conn = sqlite3.connect(self.abs_db_path)
#             self.cursor = self.conn.cursor()
#             self.create_or_migrate_table()
#             print(f"DEBUG: Connected to database {self.abs_db_path}")
#         except sqlite3.OperationalError as e:
#             print(f"DEBUG: Error connecting to database {self.abs_db_path}: {e}")
#             raise

#         # Initialize queue and thread
#         self.queue = queue.Queue(maxsize=100)  # Bounded queue
#         self._stop_event = threading.Event()  # Event to stop thread
#         self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)

#         # Create table on init
#         self._create_or_migrate_table()

#         # Start log processing thread
#         self._worker_thread.start()
        
#     def create_or_migrate_table(self):
#         try:
#             self.cursor.execute("""
#                 CREATE TABLE IF NOT EXISTS logs (
#                     id INTEGER PRIMARY KEY AUTOINCREMENT,
#                     timestamp TEXT,
#                     event TEXT,
#                     frame_path TEXT,
#                     screen_path TEXT,
#                     confidence TEXT,
#                     active_apps TEXT,
#                     username TEXT
#                 )
#             """)
#             self.cursor.execute("PRAGMA table_info(logs)")
#             columns = [col[1] for col in self.cursor.fetchall()]
#             print(f"DEBUG: Columns in logs table: {columns}")
#             if "confidence" not in columns:
#                 self.cursor.execute("ALTER TABLE logs ADD COLUMN confidence TEXT")
#                 print("DEBUG: Added confidence column")
#             if "active_apps" not in columns:
#                 self.cursor.execute("ALTER TABLE logs ADD COLUMN active_apps TEXT")
#                 print("DEBUG: Added active_apps column")
#             if "username" not in columns:
#                 self.cursor.execute("ALTER TABLE logs ADD COLUMN username TEXT")
#                 print("DEBUG: Added username column")
#             self.conn.commit()
#         except sqlite3.Error as e:
#             print(f"DEBUG: Error creating/migrating table: {e}")
#             raise

#     def _create_or_migrate_table(self):
#         """Create or migrate table in database."""
#         try:
#             conn = sqlite3.connect(self.abs_db_path)
#             cursor = conn.cursor()
#             cursor.execute("""
#                 CREATE TABLE IF NOT EXISTS logs (
#                     id INTEGER PRIMARY KEY AUTOINCREMENT,
#                     timestamp TEXT,
#                     event TEXT,
#                     frame_path TEXT,
#                     screen_path TEXT,
#                     confidence TEXT,
#                     active_apps TEXT,
#                     username TEXT
#                 )
#             """)
#             cursor.execute("PRAGMA table_info(logs)")
#             columns = [col[1] for col in cursor.fetchall()]
#             logger.debug(f"Columns in logs table: {columns}")
#             if "confidence" not in columns:
#                 cursor.execute("ALTER TABLE logs ADD COLUMN confidence TEXT")
#                 logger.debug("Added confidence column")
#             if "active_apps" not in columns:
#                 cursor.execute("ALTER TABLE logs ADD COLUMN active_apps TEXT")
#                 logger.debug("Added active_apps column")
#             if "username" not in columns:
#                 cursor.execute("ALTER TABLE logs ADD COLUMN username TEXT")
#                 logger.debug("Added username column")
#             conn.commit()
#         except sqlite3.Error as e:
#             logger.error(f"Error creating/migrating table: {e}")
#             raise
#         finally:
#             cursor.close()
#             conn.close()

#     def _worker_loop(self):
#         """Logging task processing loop in a separate thread."""
#         # Create a single database connection in this thread
#         conn = sqlite3.connect(self.abs_db_path)
#         cursor = conn.cursor()

#         while not self._stop_event.is_set():
#             try:
#                 # Wait for task from queue with timeout
#                 task = self.queue.get(timeout=1.0)
#                 timestamp, event, frame_path, screen_path, username, confidence, active_apps = task

#                 # Prepare data for database
#                 confidence_json = json.dumps(confidence) if confidence is not None else None
#                 active_apps_json = json.dumps(active_apps) if active_apps is not None else None

#                 logger.debug(f"Logging event: event={event}, frame_path={frame_path}, screen_path={screen_path}, confidence={confidence_json}, active_apps={active_apps_json}, username={username}")

#                 # Write to database
#                 try:
#                     cursor.execute(
#                         "INSERT INTO logs (timestamp, event, frame_path, screen_path, confidence, active_apps, username) VALUES (?, ?, ?, ?, ?, ?, ?)",
#                         (timestamp.replace("_", " "), event, frame_path, screen_path, confidence_json, active_apps_json, username)
#                     )
#                     conn.commit()
#                     logger.debug(f"Event successfully logged to database: id={cursor.lastrowid}, username={username}")
#                 except sqlite3.Error as e:
#                     logger.warning(f"Error writing to database: {e}")

#                 # Mark task as done
#                 self.queue.task_done()

#             except queue.Empty:
#                 continue
#             except Exception as e:
#                 logger.error(f"Error in worker loop: {e}")

#         # Close connection on stop
#         cursor.close()
#         conn.close()
#         logger.debug("Logger worker thread stopped")

#     def log_event(self, event, frame, screen, username, logger, timestamp: str, confidence=None, active_apps=None):
#         """
#         Logging the event: saves images to disk and enqueues a task.
#         """
#         logger.debug(f"logger start with event={event}")

#         # Prepare event slug
#         event_slug = self.event_slugs.get(event, event.lower().replace(" ", "_"))

#         # Prepare image paths
#         frame_path = f"logs/{timestamp}_{event_slug}.jpg"  # Relative path
#         abs_frame_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', frame_path))
#         screen_path = f"logs/{timestamp}_{event_slug}_screen.jpg"  # Relative path
#         abs_screen_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', screen_path))
#         os.makedirs(os.path.dirname(abs_frame_path), exist_ok=True)

#         # Save images
#         if frame is not None:
#             try:
#                 cv2.imwrite(abs_frame_path, frame)
#                 logger.debug(f"Saved frame: {abs_frame_path}")
#             except Exception as e:
#                 logger.debug(f"Error saving frame {abs_frame_path}: {e}")
#                 frame_path = None
#         else:
#             logger.debug(f"Frame is None, skipping save for {abs_frame_path}")
#             frame_path = None

#         if screen is not None:
#             try:
#                 cv2.imwrite(abs_screen_path, screen)
#                 logger.debug(f"Saved screen: {abs_screen_path}")
#             except Exception as e:
#                 logger.debug(f"Error saving screen {abs_screen_path}: {e}")
#                 screen_path = None
#         else:
#             logger.debug(f"Screen is None, skipping save for {abs_screen_path}")
#             screen_path = None

#         # Put task in queue
#         try:
#             self.queue.put(
#                 (timestamp, event, frame_path, screen_path, username, confidence, active_apps),
#                 timeout=2.0
#             )
#         except queue.Full:
#             logger.warning("Logging queue is full, dropping event")
#             # Delete temp files if created
#             if frame_path and os.path.exists(abs_frame_path):
#                 try:
#                     os.remove(abs_frame_path)
#                     logger.debug(f"Deleted unsaved frame: {abs_frame_path}")
#                 except OSError as e:
#                     logger.debug(f"Error deleting frame {abs_frame_path}: {e}")
#             if screen_path and os.path.exists(abs_screen_path):
#                 try:
#                     os.remove(abs_screen_path)
#                     logger.debug(f"Deleted unsaved screen: {abs_screen_path}")
#                 except OSError as e:
#                     logger.debug(f"Error deleting screen {abs_screen_path}: {e}")

#     def get_logs(self):
#         """Get all logs from database."""
#         # Create new connection for reading, as this may be called from another thread
#         conn = sqlite3.connect(self.abs_db_path)
#         cursor = conn.cursor()
#         try:
#             cursor.execute("SELECT * FROM logs ORDER BY timestamp DESC")
#             logs = cursor.fetchall()
#             logger.debug(f"Loaded {len(logs)} logs from database")
#             for log in logs:
#                 logger.debug(f"Log: id={log[0]}, timestamp={log[1]}, event={log[2]}, frame_path={log[3]}, screen_path={log[4]}, confidence={log[5]}, active_apps={log[6]}, username={log[7]}")
#             return logs
#         except sqlite3.Error as e:
#             logger.error(f"Error reading logs from database: {e}")
#             return []
#         finally:
#             cursor.close()
#             conn.close()

#     def clean_old_logs(self, retention_period):
#         """Clean old logs and associated files."""
#         if retention_period == "Never delete":
#             return
#         periods = {
#             "1 day": timedelta(days=1),
#             "1 week": timedelta(weeks=1),
#             "1 month": timedelta(days=30),
#             "1 year": timedelta(days=365)
#         }
#         if retention_period not in periods:
#             return
#         cutoff = datetime.now() - periods[retention_period]
#         cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")

#         # Create new connection for cleanup
#         conn = sqlite3.connect(self.abs_db_path)
#         cursor = conn.cursor()
#         try:
#             cursor.execute("SELECT frame_path, screen_path FROM logs WHERE timestamp < ?", (cutoff_str,))
#             paths = cursor.fetchall()
#             for frame_path, screen_path in paths:
#                 for path in (frame_path, screen_path):
#                     if path:
#                         abs_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', path))
#                         try:
#                             if os.path.exists(abs_path):
#                                 os.remove(abs_path)
#                                 logger.debug(f"Deleted old file: {abs_path}")
#                         except OSError as e:
#                             logger.debug(f"Error deleting file {abs_path}: {e}")
#             cursor.execute("DELETE FROM logs WHERE timestamp < ?", (cutoff_str,))
#             conn.commit()
#             logger.debug(f"Deleted logs older than {cutoff_str}")
#         except sqlite3.Error as e:
#             logger.error(f"Error cleaning old logs: {e}")
#         finally:
#             cursor.close()
#             conn.close()

#     def close(self):
#         """Stop processing thread and release resources."""
#         logger.debug("Stopping Logger")
#         self._stop_event.set()
#         self._worker_thread.join(timeout=2.0)  # Wait for thread to finish
#         logger.debug("Logger stopped")

#     def __del__(self):
#         """Guaranteed cleanup on object deletion."""
#         self.close()
