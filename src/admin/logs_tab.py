import os
import json
import sqlite3
from datetime import datetime, timedelta
import cv2
import logging
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QComboBox, QLabel, QDateEdit, QTimeEdit, QPushButton,
    QMessageBox, QDialog, QScrollArea
)
from PyQt5.QtGui import QPixmap, QImage, QIcon, QColor
from PyQt5.QtCore import Qt, QDate, QTime, QTimer
from src.core.logger import Logger
from src.admin.styles import ThemeManager, ThemeConstants
from src.admin.utils import get_image_path, get_resource_path

logging.basicConfig(level=logging.CRITICAL+1, format='%(asctime)s %(levelname)s:%(message)s')
logger = logging.getLogger(__name__)

class ImageDialog(QDialog):
    def __init__(self, logs, current_index, parent=None):
        super().__init__(parent, Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        self.logs = logs
        self.current_index = current_index
        self.logger = Logger()
        self.theme_manager = ThemeManager()
        self.setWindowTitle("Event Viewer")
        self.setMinimumSize(900, 700)
        self.layout = QHBoxLayout()
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {self.theme_manager.get_theme().surface};
                border: 1px solid {self.theme_manager.get_theme().outline};
                border-radius: {self.theme_manager.constants.corner_radius_large}px;
            }}
        """)

        # Left navigation
        nav_left = QVBoxLayout()
        arrow_left_path = get_resource_path('assets/arrow_left_v2.png')
        logger.debug(f"Loading arrow_left: {arrow_left_path}, exists={os.path.exists(arrow_left_path)}")
        self.prev_button = QPushButton()
        self.prev_button.setIcon(QIcon(arrow_left_path))
        self.prev_button.setFixedSize(32, 32)
        self.prev_button.setStyleSheet(self.theme_manager.get_button_stylesheet("primary"))
        self.prev_button.clicked.connect(self.show_previous)
        nav_left.addStretch()
        nav_left.addWidget(self.prev_button)
        nav_left.addStretch()
        self.layout.addLayout(nav_left)

        # Content layout
        content_layout = QVBoxLayout()

        # Images layout
        images_layout = QHBoxLayout()
        self.frame_label = QLabel()
        self.frame_label.setAlignment(Qt.AlignCenter)
        self.frame_label.setStyleSheet(f"""
            border: 1px solid {self.theme_manager.get_theme().outline};
            border-radius: {self.theme_manager.constants.corner_radius_small}px;
            background-color: #111;
        """)
            # padding: {self.theme_manager.constants.padding_small}px;
            # background-color: {self.theme_manager.get_theme().surface};
        self.frame_label.setCursor(Qt.PointingHandCursor)
        self.frame_label.mousePressEvent = lambda x: self.open_fullscreen("frame")
        images_layout.addWidget(self.frame_label)

        self.screen_label = QLabel()
        self.screen_label.setAlignment(Qt.AlignCenter)
        self.screen_label.setStyleSheet(f"""
            border: 1px solid {self.theme_manager.get_theme().outline};
            border-radius: {self.theme_manager.constants.corner_radius_small}px;
            background-color: #111;
        """)
            # padding: {self.theme_manager.constants.padding_small}px;
            # background-color: {self.theme_manager.get_theme().surface};
        self.screen_label.setCursor(Qt.PointingHandCursor)
        self.screen_label.mousePressEvent = lambda x: self.open_fullscreen("screen")
        images_layout.addWidget(self.screen_label)
        content_layout.addLayout(images_layout)

        # Text description
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet(self.theme_manager.get_label_stylesheet())
        content_layout.addWidget(self.summary_label)
        self.layout.addLayout(content_layout)

        # Right navigation
        nav_right = QVBoxLayout()
        arrow_right_path = get_resource_path('assets/arrow_right_v2.png')
        logger.debug(f"Loading arrow_right: {arrow_right_path}, exists={os.path.exists(arrow_right_path)}")
        self.next_button = QPushButton()
        self.next_button.setIcon(QIcon(arrow_right_path))
        self.next_button.setFixedSize(32, 32)
        self.next_button.setStyleSheet(self.theme_manager.get_button_stylesheet("primary"))
        self.next_button.clicked.connect(self.show_next)
        nav_right.addStretch()
        nav_right.addWidget(self.next_button)
        nav_right.addStretch()
        self.layout.addLayout(nav_right)

        self.setLayout(self.layout)
        self.layout.setContentsMargins(
            self.theme_manager.constants.padding_large,
            self.theme_manager.constants.padding_large,
            self.theme_manager.constants.padding_large,
            self.theme_manager.constants.padding_large
        )
        self.update_display()

    def update_display(self) -> None:
        """Updates the dialog display with the current log."""
        log = self.logs[self.current_index]
        timestamp, event, frame_path, screen_path, confidence, active_apps, username, device = log[1], log[2], log[3], log[4], log[5], log[6], log[7], log[8]
        abs_frame_path = self.logger._get_log_file_path(frame_path) if frame_path else ""
        abs_screen_path = self.logger._get_log_file_path(screen_path) if screen_path else ""
        logger.debug(f"Loading images: frame_path={abs_frame_path}, screen_path={abs_screen_path}")

        # Loading frame
        frame_image = cv2.imread(abs_frame_path)
        if frame_image is not None:
            frame_image = cv2.cvtColor(frame_image, cv2.COLOR_BGR2RGB)
            height, width, channel = frame_image.shape
            qimage = QImage(frame_image.data, width, height, width * channel, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qimage).scaled(400, 300, Qt.KeepAspectRatio)
            self.frame_label.setPixmap(pixmap)
        else:
            self.frame_label.setText("Failed to load frame")

        # Loading screen
        screen_image = cv2.imread(abs_screen_path)
        if screen_image is not None:
            screen_image = cv2.cvtColor(screen_image, cv2.COLOR_BGR2RGB)
            height, width, channel = screen_image.shape
            qimage = QImage(screen_image.data, width, height, width * channel, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qimage).scaled(400, 300, Qt.KeepAspectRatio)
            self.screen_label.setPixmap(pixmap)
        else:
            self.screen_label.setText("Failed to load screen")

        # Text description
        try:
            confidence = json.loads(confidence) if confidence else None
            active_apps = json.loads(active_apps) if active_apps else None
        except (json.JSONDecodeError, TypeError):
            confidence, active_apps = None, None

        confidence_text = ", ".join([f"{c:.2f}" for c in confidence]) if confidence else "None"
        apps_text = ""
        if active_apps:
            for app in active_apps:
                status = " (maximized)" if app.get("foreground") else ""
                process = app.get("process", "")
                title = app.get("title", "")
                apps_text += f"{process}: {title}{status}\n"
        apps_text = apps_text.strip() or "None"

        summary = (
            f"Time: {timestamp}\n"
            f"Event: {event}\n"
            f"Confidence: {confidence_text}\n"
            f"Running apps:\n{apps_text}\n"
            f"Device: {device}\n"
            f"User: {username}"
        )
        self.summary_label.setText(summary)

        self.prev_button.setEnabled(self.current_index > 0)
        self.next_button.setEnabled(self.current_index < len(self.logs) - 1)

    def open_fullscreen(self, event: str = "frame") -> None:
        """Opens fullscreen image view."""
        log = self.logs[self.current_index]
        frame_path = self.logger._get_log_file_path(log[3]) if log[3] else ""
        screen_path = self.logger._get_log_file_path(log[4]) if log[4] else ""
        fullscreen_dialog = FullScreenImageDialog(frame_path, screen_path, self)
        fullscreen_dialog.current_image = event
        fullscreen_dialog.update_image()
        fullscreen_dialog.exec_()

    def show_previous(self) -> None:
        """Shows the previous log."""
        if self.current_index > 0:
            self.current_index -= 1
            self.update_display()

    def show_next(self) -> None:
        """Shows the next log."""
        if self.current_index < len(self.logs) - 1:
            self.current_index += 1
            self.update_display()

class FullScreenImageDialog(QDialog):
    def __init__(self, frame_path: str, screen_path: str, parent=None) -> None:
        super().__init__(parent, Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        self.frame_path = frame_path
        self.screen_path = screen_path
        self.current_image = "frame"
        self.theme_manager = ThemeManager()
        self.setWindowTitle("Image Viewer")
        screen_size = QApplication.desktop().availableGeometry().size()
        self.resize(int(screen_size.width() * 0.8), int(screen_size.height() * 0.8))
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {self.theme_manager.get_theme().surface};
                border: 1px solid {self.theme_manager.get_theme().outline};
                border-radius: {self.theme_manager.constants.corner_radius_large}px;
            }}
        """)

        self.layout = QVBoxLayout()
        self.title_label = QLabel("Frame")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet(f"""
            color: {self.theme_manager.get_theme().on_surface};
            font-family: {self.theme_manager.typography.font_family};
            font-size: {self.theme_manager.typography.label_medium}px;
            font-weight: {self.theme_manager.typography.font_weight_medium};
            background-color: {self.theme_manager.get_theme().primary_container};
            padding: {self.theme_manager.constants.padding_small}px;
            border-radius: {self.theme_manager.constants.corner_radius_small}px;
        """)
        self.layout.addWidget(self.title_label)

        content_layout = QHBoxLayout()
        nav_left = QVBoxLayout()
        arrow_left_path = get_resource_path('assets/arrow_left_v2.png')
        self.prev_button = QPushButton()
        self.prev_button.setIcon(QIcon(arrow_left_path))
        self.prev_button.setFixedSize(32, 32)
        self.prev_button.setStyleSheet(self.theme_manager.get_button_stylesheet("primary"))
        self.prev_button.clicked.connect(self.show_previous_image)
        nav_left.addStretch()
        nav_left.addWidget(self.prev_button)
        nav_left.addStretch()
        content_layout.addLayout(nav_left)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.scroll_area.setWidget(self.image_label)
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background-color: #000000;
            }}
        """)
                # border-radius: {self.theme_manager.constants.corner_radius_small}px;
                # border: 1px solid {self.theme_manager.get_theme().outline};
        content_layout.addWidget(self.scroll_area)

        nav_right = QVBoxLayout()
        arrow_right_path = get_resource_path('assets/arrow_right_v2.png')
        self.next_button = QPushButton()
        self.next_button.setIcon(QIcon(arrow_right_path))
        self.next_button.setFixedSize(32, 32)
        self.next_button.setStyleSheet(self.theme_manager.get_button_stylesheet("primary"))
        self.next_button.clicked.connect(self.show_next_image)
        nav_right.addStretch()
        nav_right.addWidget(self.next_button)
        nav_right.addStretch()
        content_layout.addLayout(nav_right)

        self.layout.addLayout(content_layout)
        self.setLayout(self.layout)
        self.layout.setContentsMargins(
            self.theme_manager.constants.padding_large,
            self.theme_manager.constants.padding_large,
            self.theme_manager.constants.padding_large,
            self.theme_manager.constants.padding_large
        )

    def showEvent(self, event) -> None:
        """Handles the window show event."""
        super().showEvent(event)
        QTimer.singleShot(0, self.update_image)

    def update_image(self) -> None:
        """Updates the displayed image in full size with black borders."""
        image_path = self.frame_path if self.current_image == "frame" else self.screen_path
        logger.debug(f"Loading fullscreen image: {image_path}")
        
        if not os.path.exists(image_path):
            logger.debug(f"Image file does not exist: {image_path}")
            self.image_label.setText(f"Failed to load {self.current_image}")
            self.image_label.setStyleSheet("color: white; background-color: #000000;")
            return

        image = cv2.imread(image_path)
        if image is not None:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            height, width, channel = image.shape
            qimage = QImage(image.data, width, height, width * channel, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qimage).scaled(
                self.scroll_area.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.image_label.setPixmap(pixmap)
            self.image_label.setStyleSheet("background-color: #000000;")
            self.image_label.adjustSize()
        else:
            self.image_label.setText(f"Failed to load {self.current_image}")
            self.image_label.setStyleSheet("color: white; background-color: #000000;")

        self.title_label.setText("Frame" if self.current_image == "frame" else "Screenshot")
        self.prev_button.setEnabled(True)
        self.next_button.setEnabled(True)

    def show_previous_image(self) -> None:
        """Switches to the previous image."""
        self.current_image = "frame" if self.current_image == "screen" else "screen"
        self.update_image()

    def show_next_image(self) -> None:
        """Switches to the next image."""
        self.current_image = "screen" if self.current_image == "frame" else "frame"
        self.update_image()

    def keyPressEvent(self, event) -> None:
        """Handles key presses."""
        if event.key() == Qt.Key_Escape:
            self.close()
        elif event.key() == Qt.Key_Left:
            self.show_previous_image()
        elif event.key() == Qt.Key_Right:
            self.show_next_image()

class LogsTab(QWidget):
    def __init__(self):
        super().__init__()
        self.logger = Logger()
        self.theme_manager = ThemeManager()
        self.constants = ThemeConstants()
        self.init_logs_tab()

    def init_logs_tab(self) -> None:
        """Initializes the logs tab."""
        logger.debug("Initializing logs tab")
        self.logs_layout = QVBoxLayout()
        self.logs_layout.setSpacing(self.constants.padding_large)
        self.logs_layout.setContentsMargins(
            self.constants.padding_large, self.constants.padding_large,
            self.constants.padding_large, self.constants.padding_large
        )
        self.setStyleSheet(self.theme_manager.get_widget_stylesheet())
        self.create_top_filters()
        self.create_bottom_filters()
        self.create_logs_table()
        self.create_no_logs_label()
        self.setLayout(self.logs_layout)
        self.load_logs()

    def create_top_filters(self) -> None:
        """Creates the top filter row."""
        filter_layout_top = QHBoxLayout()
        
        event_label = QLabel("Event filter:")
        event_label.setStyleSheet(self.theme_manager.get_label_stylesheet())
        self.event_filter = QComboBox()
        self.event_filter.addItems([
            "All events", "Mobile phone detected", "Monochromatic image",
            "After monochromatic image", "Camera connection lost",
            "Recovered from camera connection loss", "Attempt to close application",
            "Frozen image", "Image unfrozen"
        ])
        self.event_filter.currentTextChanged.connect(self.load_logs)
        self.event_filter.setStyleSheet(self.theme_manager.get_combobox_stylesheet())
        filter_layout_top.addWidget(event_label)
        filter_layout_top.addWidget(self.event_filter)
        
        device_label = QLabel("Device:")
        device_label.setStyleSheet(self.theme_manager.get_label_stylesheet())
        self.device_filter = QComboBox()
        self.device_filter.addItem("All devices")
        self.load_devices()
        self.device_filter.currentTextChanged.connect(self.load_logs)
        self.device_filter.setStyleSheet(self.theme_manager.get_combobox_stylesheet())
        filter_layout_top.addWidget(device_label)
        filter_layout_top.addWidget(self.device_filter)

        user_label = QLabel("User:")
        user_label.setStyleSheet(self.theme_manager.get_label_stylesheet())
        self.user_filter = QComboBox()
        self.user_filter.addItem("All users")
        self.load_users()
        self.user_filter.currentTextChanged.connect(self.load_logs)
        self.user_filter.setStyleSheet(self.theme_manager.get_combobox_stylesheet())
        filter_layout_top.addWidget(user_label)
        filter_layout_top.addWidget(self.user_filter)

        filter_layout_top.addStretch()
        self.logs_layout.addLayout(filter_layout_top)

    def create_bottom_filters(self) -> None:
        """Creates the bottom filter row."""
        filter_layout_bottom = QHBoxLayout()
        period_label = QLabel("Period:")
        period_label.setStyleSheet(self.theme_manager.get_label_stylesheet())
        self.date_filter = QComboBox()
        self.date_filter.addItems(["All time", "Today", "Week", "Month", "Select period"])
        self.date_filter.setCurrentText("All time")
        self.date_filter.currentTextChanged.connect(self.on_date_filter_changed)
        self.date_filter.setStyleSheet(self.theme_manager.get_combobox_stylesheet())
        filter_layout_bottom.addWidget(period_label)
        filter_layout_bottom.addWidget(self.date_filter)

        date_from_label = QLabel("From:")
        date_from_label.setStyleSheet(self.theme_manager.get_label_stylesheet())
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setSpecialValueText("__.__.____")
        self.date_from.setDate(QDate.currentDate())
        self.date_from.setDisplayFormat("dd.MM.yyyy")
        self.date_from.setStyleSheet(self.theme_manager.get_date_edit_stylesheet())
        self.date_from.setEnabled(False)
        filter_layout_bottom.addWidget(date_from_label)
        filter_layout_bottom.addWidget(self.date_from)

        time_from_label = QLabel("Time from:")
        time_from_label.setStyleSheet(self.theme_manager.get_label_stylesheet())
        self.time_from = QTimeEdit()
        self.time_from.setDisplayFormat("HH:mm:ss")
        self.time_from.setTime(QTime(0, 0, 0))
        self.time_from.setMinimumWidth(115)
        self.time_from.setStyleSheet(self.theme_manager.get_date_edit_stylesheet())
        self.time_from.setEnabled(False)
        filter_layout_bottom.addWidget(time_from_label)
        filter_layout_bottom.addWidget(self.time_from)

        date_to_label = QLabel("To:")
        date_to_label.setStyleSheet(self.theme_manager.get_label_stylesheet())
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setSpecialValueText("__.__.____")
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setDisplayFormat("dd.MM.yyyy")
        self.date_to.setStyleSheet(self.theme_manager.get_date_edit_stylesheet())
        self.date_to.setEnabled(False)
        filter_layout_bottom.addWidget(date_to_label)
        filter_layout_bottom.addWidget(self.date_to)

        time_to_label = QLabel("Time to:")
        time_to_label.setStyleSheet(self.theme_manager.get_label_stylesheet())
        self.time_to = QTimeEdit()
        self.time_to.setDisplayFormat("HH:mm:ss")
        self.time_to.setTime(QTime(23, 59, 59))
        self.time_to.setMinimumWidth(115)
        self.time_to.setStyleSheet(self.theme_manager.get_date_edit_stylesheet())
        self.time_to.setEnabled(False)
        filter_layout_bottom.addWidget(time_to_label)
        filter_layout_bottom.addWidget(self.time_to)

        filter_layout_bottom.addStretch()
        self.refresh_button = QPushButton("Refresh Logs")
        self.refresh_button.clicked.connect(self.load_logs)
        self.refresh_button.setStyleSheet(self.theme_manager.get_button_stylesheet("primary"))
        filter_layout_bottom.addWidget(self.refresh_button)

        self.clear_button = QPushButton("Clear Logs")
        self.clear_button.clicked.connect(self.clear_logs)
        self.clear_button.setStyleSheet(self.theme_manager.get_button_stylesheet("error"))
        filter_layout_bottom.addWidget(self.clear_button)

        self.logs_layout.addLayout(filter_layout_bottom)

    def create_logs_table(self) -> None:
        """Creates the logs table."""
        self.logs_table = QTableWidget()
        self.logs_table.setStyleSheet(self.theme_manager.get_table_stylesheet())
        self.logs_table.setColumnCount(8)
        self.logs_table.setHorizontalHeaderLabels([
            "Time", "Event", "Confidence", "Running Apps",
            "Device", "User", "Thumbnail", "Screenshot"
        ])
        self.logs_table.verticalHeader().setDefaultSectionSize(56)
        self.logs_table.horizontalHeader().setMinimumHeight(56)
        self.logs_table.setSortingEnabled(True)
        self.logs_table.setWordWrap(True)
        column_widths = [120, 220, 115, 300, 115, 120, 200, 200]
        for i in range(self.logs_table.columnCount()):
            self.logs_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.Interactive)
            self.logs_table.setColumnWidth(i, column_widths[i])
        self.logs_table.setMinimumWidth(1450)
        self.logs_table.setSelectionMode(QTableWidget.SingleSelection)
        self.logs_table.setEditTriggers(QTableWidget.NoEditTriggers)
        logger.debug("Connecting cellClicked signal")
        self.logs_table.cellClicked.connect(self.on_cell_clicked)
        self.logs_layout.addWidget(self.logs_table)

    def create_no_logs_label(self) -> None:
        """Creates the no-logs label."""
        self.no_logs_label = QLabel("No events")
        self.no_logs_label.setAlignment(Qt.AlignCenter)
        self.no_logs_label.setStyleSheet(self.theme_manager.get_label_stylesheet())
        self.no_logs_label.setVisible(False)
        self.logs_layout.addWidget(self.no_logs_label)
        
    def on_cell_clicked(self, row: int, column: int) -> None:
        """Handles table cell click, opening the event viewer."""
        logger.debug(f"Cell clicked: row={row}, column={column}")
        logs = self.logger.get_logs()
        if logs and row < len(logs):
            dialog = ImageDialog(logs, row, self)
            dialog.exec_()

    # def on_cell_clicked(self, row: int, column: int) -> None:
    #     """Handles table cell click."""
    #     logger.debug(f"Cell clicked: row={row}, column={column}")
    #     # if column in (5, 6):
    #     item = self.logs_table.item(row, column)
    #     if item and item.data(Qt.UserRole) is not None:
    #         logs = self.logger.get_logs()
    #         if logs:
    #             dialog = ImageDialog(logs, row, self)
    #             dialog.exec_()

    def clear_logs(self) -> None:
        """Clears logs and associated files."""
        reply = QMessageBox.question(
            self, "Confirm", "Are you sure you want to clear the Event Log?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                self.logger.cursor.execute("SELECT frame_path FROM logs")
                frame_paths = [row[0] for row in self.logger.cursor.fetchall()]
                for frame_path in frame_paths:
                    if frame_path:
                        abs_frame_path = get_image_path(frame_path)
                        try:
                            if os.path.exists(abs_frame_path):
                                os.remove(abs_frame_path)
                                logger.debug(f"Deleted frame: {abs_frame_path}")
                        except OSError as e:
                            logger.debug(f"Error deleting frame {abs_frame_path}: {e}")

                self.logger.cursor.execute("DELETE FROM logs")
                self.logger.conn.commit()
                logger.debug("All logs cleared")
                self.load_logs()
                self.load_users()
                QMessageBox.information(self, "Log cleared", "Event Log has been successfully cleared.")
            except Exception as e:
                logger.debug(f"Error clearing logs: {e}")
                QMessageBox.critical(self, "Error", "Failed to clear logs.")
        else:
            QMessageBox.information(self, "Log cleared", "Log clear cancelled.")

    def on_date_filter_changed(self) -> None:
        """Handles period filter change."""
        is_custom_period = (self.date_filter.currentText() == "Select period")
        self.date_from.setEnabled(is_custom_period)
        self.date_to.setEnabled(is_custom_period)
        self.time_from.setEnabled(is_custom_period)
        self.time_to.setEnabled(is_custom_period)
        self.load_logs()
        
    def load_devices(self) -> None:
        """Loads device list from logs"""
        try:
            self.logger.cursor.execute("SELECT DISTINCT device FROM logs WHERE device IS NOT NULL")
            devices = [row[0] for row in self.logger.cursor.fetchall()]
            for device in devices:
                self.device_filter.addItem(device)
            logger.debug(f"Loaded devices: {devices}")
        except Exception as e:
            logger.debug(f"Error loading devices: {e}")
        
    def load_users(self) -> None:
        """Loads user list from logs."""
        try:
            self.logger.cursor.execute("SELECT DISTINCT username FROM logs WHERE username IS NOT NULL")
            users = [row[0] for row in self.logger.cursor.fetchall()]
            for user in users:
                self.user_filter.addItem(user)
            logger.debug(f"Loaded users: {users}")
        except Exception as e:
            logger.debug(f"Error loading users: {e}")

    def load_logs(self) -> None:
        """Loads logs into the table with filters applied."""
        logger.debug(f"Loading logs... Current directory: {os.getcwd()}")
        self.logs_table.clearContents()
        self.no_logs_label.setVisible(False)
        event_filter = self.event_filter.currentText()
        user_filter = self.user_filter.currentText()
        device_filter = self.device_filter.currentText()
        date_filter = self.date_filter.currentText()
        theme = self.theme_manager.get_theme()
        try:
            self.logger.cursor.execute("PRAGMA table_info(logs)")
            columns = [col[1] for col in self.logger.cursor.fetchall()]
            logger.debug(f"Columns in logs table: {columns}")

            conditions = []
            params = []
            if event_filter != "All events":
                conditions.append("event = ?")
                params.append(event_filter)
            if user_filter != "All users":
                conditions.append("username = ?")
                params.append(user_filter)
            if device_filter != "All devices":
                conditions.append("device = ?")
                params.append(device_filter)
            if date_filter != "All time":
                if date_filter == "Select period":
                    date_from = self.date_from.date().toString("yyyy-MM-dd")
                    time_from = self.time_from.time().toString("HH-mm-ss")
                    date_to = self.date_to.date().toString("yyyy-MM-dd")
                    time_to = self.time_to.time().toString("HH-mm-ss")
                    datetime_from = f"{date_from} {time_from}"
                    datetime_to = f"{date_to} {time_to}"
                    conditions.append("timestamp BETWEEN ? AND ?")
                    params.extend([datetime_from, datetime_to])
                else:
                    cutoff = datetime.now()
                    if date_filter == "Today":
                        cutoff = cutoff.replace(hour=0, minute=0, second=0, microsecond=0)
                    elif date_filter == "Week":
                        cutoff -= timedelta(weeks=1)
                    elif date_filter == "Month":
                        cutoff -= timedelta(days=30)
                    conditions.append("timestamp >= ?")
                    params.append(cutoff.strftime("%Y-%m-%d %H-%M-%S"))

            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
            query = f"SELECT * FROM logs {where_clause} ORDER BY timestamp DESC"
            self.logger.cursor.execute(query, params)
            logger.debug(f"Executed query: {query} with params={params}")

            logs = self.logger.cursor.fetchall()
            logger.debug(f"Loaded {len(logs)} logs for event='{event_filter}', user='{user_filter}', date='{date_filter}'")

            if not logs:
                self.logs_table.setRowCount(0)
                self.no_logs_label.setVisible(True)
                return

            self.logs_table.setRowCount(len(logs))
            for row, log in enumerate(logs):
                timestamp = log[1] if len(log) > 1 else ""
                event = log[2] if len(log) > 2 else ""
                frame_path = log[3] if len(log) > 3 else ""
                screen_path = log[4] if len(log) > 3 else ""
                confidence = log[5] if len(log) > 4 else None
                active_apps = log[6] if len(log) > 5 else None
                username = log[7] if len(log) > 6 else ""
                device = log[8] if len(log) > 7 else ""

                abs_frame_path = get_image_path(frame_path) if frame_path else ""
                if frame_path:
                    logger.debug(f"Checking path: frame_path={frame_path}, abs_path={abs_frame_path}, exists={os.path.exists(abs_frame_path)}")

                abs_screen_path = get_image_path(screen_path) if screen_path else ""
                if screen_path:
                    logger.debug(f"Checking path: screen_path={screen_path}, abs_path={abs_screen_path}, exists={os.path.exists(abs_screen_path)}")

                try:
                    confidence = json.loads(confidence) if confidence else None
                    active_apps = json.loads(active_apps) if active_apps else None
                except (json.JSONDecodeError, TypeError) as e:
                    logger.debug(f"Error parsing JSON for log id={log[0]}: {e}")
                    confidence, active_apps = None, None

                item = QTableWidgetItem(timestamp)
                item.setTextAlignment(Qt.AlignCenter)
                self.logs_table.setItem(row, 0, item)

                event_colors = {
                    "Mobile phone detected": "#FFD8E4",
                    "Monochromatic image": "#FFE7C9",
                    "Camera connection lost": "#FFCCBC",
                    "Attempt to close application": "#F5B7B1",
                    "Recovered from camera connection loss": "#B3E5FC",
                    "Frozen image": "#FFECB3",
                    "Image unfrozen": "#C8E6C9"
                }
                item = QTableWidgetItem(event)
                item.setTextAlignment(Qt.AlignCenter)
                if event in event_colors:
                    item.setBackground(QColor(event_colors[event]))
                item.setForeground(QColor(theme.on_surface))
                self.logs_table.setItem(row, 1, item)

                confidence_text = ", ".join([f"{c:.2f}" for c in confidence]) if confidence else ""
                item = QTableWidgetItem(confidence_text)
                item.setTextAlignment(Qt.AlignCenter)
                self.logs_table.setItem(row, 2, item)

                apps_text = ""
                if active_apps:
                    for app in active_apps:
                        status = " (maximized)" if app.get("foreground") else ""
                        process = app.get("process", "")
                        title = app.get("title", "")
                        apps_text += f"{process}: {title}{status}\n"
                item = QTableWidgetItem(apps_text.strip())
                item.setTextAlignment(Qt.AlignCenter)
                self.logs_table.setItem(row, 3, item)

                item = QTableWidgetItem(device)
                item.setTextAlignment(Qt.AlignCenter)
                self.logs_table.setItem(row, 4, item)

                item = QTableWidgetItem(username)
                item.setTextAlignment(Qt.AlignCenter)
                self.logs_table.setItem(row, 5, item)

                if frame_path and os.path.exists(abs_frame_path):
                    image = cv2.imread(abs_frame_path)
                    if image is not None:
                        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                        height, width, channel = image.shape
                        qimage = QImage(image.data, width, height, width * channel, QImage.Format_RGB888)
                        pixmap = QPixmap.fromImage(qimage).scaled(150, 150, Qt.KeepAspectRatio)
                        item = QTableWidgetItem()
                        item.setData(Qt.DecorationRole, pixmap)
                        item.setData(Qt.UserRole, row)
                        self.logs_table.setItem(row, 6, item)
                    else:
                        logger.debug(f"Error frame loading image: {abs_frame_path}")
                        item = QTableWidgetItem("Load error")
                        item.setTextAlignment(Qt.AlignCenter)
                        self.logs_table.setItem(row, 6, item)
                else:
                    logger.debug(f"Frame missing: {abs_frame_path}")
                    item = QTableWidgetItem("Thumbnail missing")
                    item.setTextAlignment(Qt.AlignCenter)
                    self.logs_table.setItem(row, 6, item)

                if screen_path and os.path.exists(abs_screen_path):
                    image = cv2.imread(abs_screen_path)
                    if image is not None:
                        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                        height, width, channel = image.shape
                        qimage = QImage(image.data, width, height, width * channel, QImage.Format_RGB888)
                        pixmap = QPixmap.fromImage(qimage).scaled(150, 150, Qt.KeepAspectRatio)
                        item = QTableWidgetItem()
                        item.setData(Qt.DecorationRole, pixmap)
                        item.setData(Qt.UserRole, row)
                        self.logs_table.setItem(row, 7, item)
                    else:
                        logger.debug(f"Error screen loading image: {abs_screen_path}")
                        item = QTableWidgetItem("Load error")
                        item.setTextAlignment(Qt.AlignCenter)
                        self.logs_table.setItem(row, 7, item)
                else:
                    logger.debug(f"Screen missing: {abs_screen_path}")
                    item = QTableWidgetItem("Thumbnail missing")
                    item.setTextAlignment(Qt.AlignCenter)
                    self.logs_table.setItem(row, 7, item)

                self.logs_table.resizeRowToContents(row)

            self.logs_table.setFixedWidth(1450)

        except sqlite3.Error as e:
            logger.debug(f"Error loading logs from database: {e}")
            self.logs_table.setRowCount(0)
            self.no_logs_label.setVisible(True)

    def switch_theme(self, theme_name: str) -> None:
        """Switches theme and updates styles."""
        self.theme_manager.set_theme(theme_name)
        self.update_styles()

    def update_styles(self) -> None:
        """Updates styles of all widgets."""
        self.setStyleSheet(self.theme_manager.get_widget_stylesheet())
        self.event_filter.setStyleSheet(self.theme_manager.get_combobox_stylesheet())
        self.user_filter.setStyleSheet(self.theme_manager.get_combobox_stylesheet())
        self.date_filter.setStyleSheet(self.theme_manager.get_combobox_stylesheet())
        self.date_from.setStyleSheet(self.theme_manager.get_date_edit_stylesheet())
        self.time_from.setStyleSheet(self.theme_manager.get_date_edit_stylesheet())
        self.date_to.setStyleSheet(self.theme_manager.get_date_edit_stylesheet())
        self.time_to.setStyleSheet(self.theme_manager.get_date_edit_stylesheet())
        self.logs_table.setStyleSheet(self.theme_manager.get_table_stylesheet())
        self.no_logs_label.setStyleSheet(self.theme_manager.get_label_stylesheet())
        self.refresh_button.setStyleSheet(self.theme_manager.get_button_stylesheet("primary"))
        self.clear_button.setStyleSheet(self.theme_manager.get_button_stylesheet("error"))