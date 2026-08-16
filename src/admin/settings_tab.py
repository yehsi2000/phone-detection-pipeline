from typing import List, Tuple, Optional
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QComboBox, QLabel,
    QPushButton, QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox,
    QLineEdit, QScrollArea
)
from PyQt5.QtGui import QPixmap, QImage, QPainter, QColor
from PyQt5.QtCore import Qt, QTimer
import os
import cv2
import numpy as np

from src.core.camera import Camera
from src.core.config import Config
from src.admin.styles import ThemeManager
from src.admin.utils import get_resource_path


class SettingsTab(QWidget):
    """Manages the settings tab in the admin panel."""

    def __init__(self, config: Config, theme_manager: ThemeManager) -> None:
        super().__init__()
        self.config: Config = config
        self.theme_manager: ThemeManager = theme_manager
        self.current_theme: str = "light"
        self.camera: Optional[Camera] = None
        self.detector: Optional[object] = None
        self.cameras: List[Tuple[int, str]] = self._scan_cameras_fallback()

        try:
            from src.core.detector import Detector
            model_path = get_resource_path("models/model.onnx")
            if os.path.exists(model_path):
                self.detector = Detector(model_path)
            else:
                self.detector = None
        except Exception as e:
            print(f"WARNING: Failed to load detection model: {e}")
            self.detector = None

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_preview)
        self._init_ui()

    def _scan_cameras_fallback(self) -> List[Tuple[int, str]]:
        cameras = Camera.list_available_cameras()
        if cameras:
            return cameras
        config_id = self.config.get("camera_id") or 0
        return [(config_id, f"Camera {config_id}")]

    def _populate_camera_combo(self) -> None:
        self.camera_combo.clear()
        camera_names = [name for _, name in self.cameras] or ["No cameras available"]
        self.camera_combo.addItems(camera_names)
        self._set_current_camera()

    def refresh_cameras(self) -> None:
        self.cameras = self._scan_cameras_fallback()
        self._populate_camera_combo()

    def _init_ui(self) -> None:
        theme = self.theme_manager.get_theme()
        self.setStyleSheet(f"QWidget {{ background-color: {theme.surface}; }}")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.setAlignment(Qt.AlignCenter)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        scroll_widget = QWidget()
        scroll_widget.setObjectName("scrollWidget")
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(10, 10, 10, 10)
        scroll_layout.setSpacing(10)
        scroll_area.setWidget(scroll_widget)
        main_layout.addWidget(scroll_area)

        column_widget = QWidget()
        column_widget.setMaximumWidth(1024)
        column_layout = QVBoxLayout(column_widget)
        column_layout.setAlignment(Qt.AlignHCenter)
        scroll_layout.addWidget(column_widget, alignment=Qt.AlignHCenter)

        scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background-color: {theme.surface};
                border: none;
            }}
            QWidget#scrollWidget {{
                background-color: {theme.surface};
            }}
            QScrollBar:vertical {{
                width: 8px;
                margin: 0px;
                background: transparent;
            }}
            QScrollBar::handle:vertical {{
                background: {theme.outline};
                min-height: 20px;
                border-radius: 4px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

        form_layout = QFormLayout()
        form_layout.setVerticalSpacing(10)
        form_layout.setHorizontalSpacing(20)

        device_layout = QHBoxLayout()
        device_label = QLabel("Device:")
        device_label.setStyleSheet(self.theme_manager.get_label_stylesheet_with_padding())
        self.camera_combo = QComboBox()
        self.camera_combo.setFixedWidth(200)
        self.camera_combo.setStyleSheet(self.theme_manager.get_combobox_stylesheet())
        self._populate_camera_combo()
        device_layout.addWidget(device_label)
        device_layout.addWidget(self.camera_combo)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setStyleSheet(self.theme_manager.get_button_stylesheet())
        self.refresh_button.setFixedWidth(80)
        self.refresh_button.clicked.connect(self.refresh_cameras)
        device_layout.addWidget(self.refresh_button)
        device_layout.addStretch()
        form_layout.addRow(device_layout)

        self.preview_label = QLabel()
        self.preview_label.setMinimumSize(720, 576)
        self.preview_label.setMaximumSize(720, 576)
        self.preview_label.setSizePolicy(
            self.preview_label.sizePolicy().Expanding,
            self.preview_label.sizePolicy().Expanding
        )
        self.preview_label.setScaledContents(False)
        self.preview_label.setAlignment(Qt.AlignCenter)
        logo_path = get_resource_path("assets/logo.png")
        try:
            pixmap = QPixmap(logo_path).scaled(
                720, 576, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            if not pixmap.isNull():
                self.preview_label.setPixmap(pixmap)
            else:
                self.preview_label.setText("No logo")
        except Exception:
            self.preview_label.setText("No logo")
        form_layout.addRow(self.preview_label)

        self.check_button = QPushButton("Check connection")
        self.check_button.setStyleSheet(self.theme_manager.get_button_stylesheet())
        self.check_button.clicked.connect(self.toggle_preview)
        form_layout.addRow(self.check_button)

        self.fps_spin = QSpinBox()
        self.fps_spin.setFixedWidth(200)
        self.fps_spin.setRange(1, 60)
        self.fps_spin.setValue(self.config.get("fps") or 2)
        self.fps_spin.setStyleSheet(self.theme_manager.get_input_stylesheet())
        fps_label = QLabel("Frame rate (FPS):")
        fps_label.setStyleSheet(self.theme_manager.get_label_stylesheet())
        form_layout.addRow(fps_label, self.fps_spin)

        self.retention_combo = QComboBox()
        self.retention_combo.setFixedWidth(200)
        self.retention_combo.setStyleSheet(self.theme_manager.get_combobox_stylesheet())
        self.retention_combo.addItems(["1 day", "1 week", "1 month", "1 year", "Never delete"])
        self.retention_combo.setCurrentText(self.config.get("log_retention") or "1 month")
        retention_label = QLabel("Log retention:")
        retention_label.setStyleSheet(self.theme_manager.get_label_stylesheet())
        form_layout.addRow(retention_label, self.retention_combo)

        self.confidence_spin = QDoubleSpinBox()
        self.confidence_spin.setFixedWidth(200)
        self.confidence_spin.setRange(0.1, 0.9)
        self.confidence_spin.setSingleStep(0.1)
        self.confidence_spin.setValue(self.config.get("confidence_threshold") or 0.6)
        self.confidence_spin.setStyleSheet(self.theme_manager.get_input_stylesheet())
        confidence_label = QLabel("Confidence level:")
        confidence_label.setStyleSheet(self.theme_manager.get_label_stylesheet())
        form_layout.addRow(confidence_label, self.confidence_spin)

        self.count_spin = QSpinBox()
        self.count_spin.setFixedWidth(200)
        self.count_spin.setRange(1, 999)
        self.count_spin.setValue(self.config.get("phone_limit") or 1)
        self.count_spin.setStyleSheet(self.theme_manager.get_input_stylesheet())
        count_label = QLabel("Reaction frame count:")
        count_label.setStyleSheet(self.theme_manager.get_label_stylesheet())
        form_layout.addRow(count_label, self.count_spin)

        lock_group = QGroupBox("Screen lock")
        lock_group.setStyleSheet(f"""
            QGroupBox {{
                border: 1px solid {theme.outline};
                border-radius: {self.theme_manager.constants.corner_radius_large}px;
                padding: {self.theme_manager.constants.padding_small}px;
                background-color: {theme.surface};
                font-family: {self.theme_manager.typography.font_family};
                font-size: {self.theme_manager.typography.label_medium}px;
                color: {theme.on_surface};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
                color: {theme.on_surface};
            }}
        """)
        lock_layout = QVBoxLayout()
        lock_layout.setSpacing(5)
        lock_events = self.config.get("lock_events") or {}
        self.lock_phone_detected = QCheckBox("Phone detection")
        self.lock_phone_detected.setChecked(lock_events.get("phone_detected", True))
        self.lock_phone_detected.setStyleSheet(self.theme_manager.get_checkbox_stylesheet())
        lock_layout.addWidget(self.lock_phone_detected)
        self.lock_camera_lost = QCheckBox("Camera connection lost")
        self.lock_camera_lost.setChecked(lock_events.get("camera_lost", True))
        self.lock_camera_lost.setStyleSheet(self.theme_manager.get_checkbox_stylesheet())
        lock_layout.addWidget(self.lock_camera_lost)
        self.lock_uniform_image = QCheckBox("Monochromatic image")
        self.lock_uniform_image.setChecked(lock_events.get("uniform_image", True))
        self.lock_uniform_image.setStyleSheet(self.theme_manager.get_checkbox_stylesheet())
        lock_layout.addWidget(self.lock_uniform_image)
        self.lock_attempt_to_close = QCheckBox("Attempt to close application")
        self.lock_attempt_to_close.setChecked(lock_events.get("attempt_to_close", False))
        self.lock_attempt_to_close.setStyleSheet(self.theme_manager.get_checkbox_stylesheet())
        lock_layout.addWidget(self.lock_attempt_to_close)
        self.lock_static_img = QCheckBox("Static image (frames unchanged for 30 seconds)")
        self.lock_static_img.setChecked(lock_events.get("static_img", True))
        self.lock_static_img.setStyleSheet(self.theme_manager.get_checkbox_stylesheet())
        lock_layout.addWidget(self.lock_static_img)
        lock_group.setLayout(lock_layout)
        form_layout.addRow(lock_group)

        log_group = QGroupBox("Event logging")
        log_group.setStyleSheet(lock_group.styleSheet())
        log_layout = QVBoxLayout()
        log_layout.setSpacing(5)
        log_events = self.config.get("log_events") or {}
        self.log_phone_detected = QCheckBox("Phone detection")
        self.log_phone_detected.setChecked(log_events.get("phone_detected", True))
        self.log_phone_detected.setStyleSheet(self.theme_manager.get_checkbox_stylesheet())
        log_layout.addWidget(self.log_phone_detected)
        self.log_camera_lost = QCheckBox("Camera connection lost")
        self.log_camera_lost.setChecked(log_events.get("camera_lost", True))
        self.log_camera_lost.setStyleSheet(self.theme_manager.get_checkbox_stylesheet())
        log_layout.addWidget(self.log_camera_lost)
        self.log_uniform_image = QCheckBox("Monochromatic image")
        self.log_uniform_image.setChecked(log_events.get("uniform_image", True))
        self.log_uniform_image.setStyleSheet(self.theme_manager.get_checkbox_stylesheet())
        log_layout.addWidget(self.log_uniform_image)
        self.log_attempt_to_close = QCheckBox("Attempt to close application")
        self.log_attempt_to_close.setChecked(log_events.get("attempt_to_close", True))
        self.log_attempt_to_close.setStyleSheet(self.theme_manager.get_checkbox_stylesheet())
        log_layout.addWidget(self.log_attempt_to_close)
        self.log_static_img = QCheckBox("Static image (frames unchanged for 30 seconds)")
        self.log_static_img.setChecked(log_events.get("static_img", True))
        self.log_static_img.setStyleSheet(self.theme_manager.get_checkbox_stylesheet())
        log_layout.addWidget(self.log_static_img)
        log_group.setLayout(log_layout)
        form_layout.addRow(log_group)

        other_group = QGroupBox("Additional")
        other_group.setStyleSheet(lock_group.styleSheet())
        other_layout = QVBoxLayout()
        other_layout.setSpacing(5)
        self.make_screen_enabled = QCheckBox("Screenshot")
        other_events = self.config.get("other_events") or {}
        self.make_screen_enabled.setChecked(other_events.get("make_screen_enabled", True))
        self.make_screen_enabled.setStyleSheet(self.theme_manager.get_checkbox_stylesheet())
        other_layout.addWidget(self.make_screen_enabled)
        self.autostart_system = QCheckBox("Auto-start on system boot")
        autostart = self.config.get("autostart") or {}
        self.autostart_system.setChecked(autostart.get("on_system_start", False))
        self.autostart_system.setStyleSheet(self.theme_manager.get_checkbox_stylesheet())
        other_layout.addWidget(self.autostart_system)
        other_group.setLayout(other_layout)
        form_layout.addRow(other_group)

        # Central Server Connection Group
        server_group = QGroupBox("Central Server Connection")
        server_group.setStyleSheet(lock_group.styleSheet())
        server_layout = QVBoxLayout()
        server_layout.setSpacing(8)

        server_url_label = QLabel("Central Server URL:")
        server_url_label.setStyleSheet(self.theme_manager.get_label_stylesheet())
        server_layout.addWidget(server_url_label)
        self.server_url_input = QLineEdit()
        self.server_url_input.setText(self.config.get("server_url") or "http://localhost:8000")
        self.server_url_input.setFixedWidth(350)
        self.server_url_input.setStyleSheet(self.theme_manager.get_input_stylesheet())
        server_layout.addWidget(self.server_url_input)

        client_id_label = QLabel("Client Device ID:")
        client_id_label.setStyleSheet(self.theme_manager.get_label_stylesheet())
        server_layout.addWidget(client_id_label)
        self.client_id_input = QLineEdit()
        self.client_id_input.setText(self.config.get("client_id") or "agent-01")
        self.client_id_input.setFixedWidth(350)
        self.client_id_input.setStyleSheet(self.theme_manager.get_input_stylesheet())
        server_layout.addWidget(self.client_id_input)

        server_group.setLayout(server_layout)
        form_layout.addRow(server_group)

        column_layout.addLayout(form_layout)

        save_button = QPushButton("Save")
        save_button.setStyleSheet(self.theme_manager.get_button_stylesheet())
        save_button.clicked.connect(self.save_settings)
        save_button.setMaximumWidth(200)
        column_layout.addWidget(save_button, alignment=Qt.AlignCenter)
        column_layout.addStretch()

    def _scale_pixmap_with_padding(self, pixmap: QPixmap, target_width: int, target_height: int) -> QPixmap:
        scaled_pixmap = pixmap.scaled(
            target_width, target_height, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        scaled_width, scaled_height = scaled_pixmap.width(), scaled_pixmap.height()
        if scaled_width == target_width and scaled_height == target_height:
            return scaled_pixmap
        result = QPixmap(target_width, target_height)
        result.fill(QColor(self.theme_manager.get_theme().surface))
        painter = QPainter(result)
        painter.drawPixmap((target_width - scaled_width) // 2, (target_height - scaled_height) // 2, scaled_pixmap)
        painter.end()
        return result

    def update_preview(self) -> None:
        if not self.camera:
            self.preview_label.setText("Camera not initialized")
            return
        frame = self.camera.get_frame()
        if frame is None:
            self.preview_label.setText("No signal")
            return

        if self.detector:
            try:
                found, bbox, confs = self.detector.detect_phone(
                    frame.copy(),
                    conf=self.config.get("confidence_threshold")
                )
                if found and bbox:
                    x1, y1, x2, y2 = bbox
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
                    label = f"Phone {confs[0]:.2f}" if confs else "Phone"
                    cv2.putText(frame, label, (x1, max(20, y1 - 10)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            except Exception as e:
                print(f"DEBUG: Detection failed: {e}")

        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, channel = frame.shape
        qimage = QImage(frame.data, width, height, width * channel, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimage)
        target_width = min(self.preview_label.width(), 720)
        target_height = min(self.preview_label.height(), 576)
        scaled_pixmap = self._scale_pixmap_with_padding(pixmap, target_width, target_height)
        self.preview_label.setPixmap(scaled_pixmap)

    def _set_current_camera(self) -> None:
        current_camera = self.config.get("camera_id")
        for i, (cam_id, _) in enumerate(self.cameras):
            if cam_id == current_camera:
                self.camera_combo.setCurrentIndex(i)
                break

    def toggle_preview(self) -> None:
        if self.timer.isActive():
            self.timer.stop()
            if self.camera:
                self.camera.release()
                self.camera = None
            logo_path = get_resource_path('assets/logo.png')
            try:
                pixmap = QPixmap(logo_path).scaled(
                    720, 576, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                if not pixmap.isNull():
                    self.preview_label.setPixmap(pixmap)
                else:
                    self.preview_label.setText("No logo")
            except Exception:
                self.preview_label.setText("No logo")
            self.check_button.setText("Check connection")
        else:
            selected_index = self.camera_combo.currentIndex()
            if not self.cameras or selected_index < 0:
                self.preview_label.setText("Camera unavailable")
                self.check_button.setText("Check connection")
                return
            camera_id = self.cameras[selected_index][0]
            try:
                self.camera = Camera(camera_id)
                self.timer.start(100)
                self.check_button.setText("Stop check")
            except Exception as e:
                self.preview_label.setText("Camera in use — close main.py first")
                self.check_button.setText("Check connection")
                print(f"DEBUG: Preview failed: {e}")

    def toggle_theme(self) -> None:
        self.current_theme = "dark" if self.current_theme == "light" else "light"
        self.theme_manager.set_theme(self.current_theme)
        self._init_ui()

    def save_settings(self) -> None:
        selected_index = self.camera_combo.currentIndex()
        camera_id = self.cameras[selected_index][0] if self.cameras and selected_index >= 0 else 0
        config = self.config.config.copy()
        config.update({
            "camera_id": camera_id,
            "fps": self.fps_spin.value(),
            "log_retention": self.retention_combo.currentText(),
            "confidence_threshold": self.confidence_spin.value(),
            "phone_limit": self.count_spin.value(),
            "server_url": self.server_url_input.text().strip(),
            "client_id": self.client_id_input.text().strip(),
            "autostart": {
                "on_system_start": self.autostart_system.isChecked(),
            },
            "lock_events": {
                "phone_detected": self.lock_phone_detected.isChecked(),
                "camera_lost": self.lock_camera_lost.isChecked(),
                "uniform_image": self.lock_uniform_image.isChecked(),
                "attempt_to_close": self.lock_attempt_to_close.isChecked(),
                "static_img": self.lock_static_img.isChecked(),
            },
            "log_events": {
                "phone_detected": self.log_phone_detected.isChecked(),
                "camera_lost": self.log_camera_lost.isChecked(),
                "uniform_image": self.log_uniform_image.isChecked(),
                "attempt_to_close": self.log_attempt_to_close.isChecked(),
                "static_img": self.log_static_img.isChecked(),
            },
            "other_events": {
                "make_screen_enabled": self.make_screen_enabled.isChecked(),
            }
        })
        self.config.save_config(config)