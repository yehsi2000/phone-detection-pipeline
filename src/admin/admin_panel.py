import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QVBoxLayout, QWidget, QDialog, QLabel, QPushButton, QHBoxLayout, QComboBox,
    QSpinBox, QDoubleSpinBox, QFormLayout, QCheckBox, QGroupBox, QMessageBox, QDateEdit,
    QFileDialog, QTimeEdit, QLineEdit, QTextEdit, QListWidget, QScrollArea
)
from PyQt5.QtGui import QPixmap, QImage, QIcon, QColor
from PyQt5.QtCore import Qt, QTimer, QDate, QTime
import json
import cv2
from src.core.logger import Logger
from src.core.camera import Camera
from src.core.config import Config
from src.infra.enable_autostart import enable_autostart, APP_NAME, get_project_main_path, disable_autostart
from src.admin.styles import ThemeManager
from src.admin.logs_tab import LogsTab
from src.admin.settings_tab import SettingsTab
from datetime import datetime, timedelta
import sqlite3
import logging

from src.infra.is_admin import is_admin, get_run_path
from src.infra.critical_error import critical_error
from src.infra.set_admin_only_acess import set_admin_only_access

from src.admin.utils import get_resource_path, get_image_path, get_base_path
# from PyQt5.QtWidgets import QDialog, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QTabWidget
# from PyQt5.QtGui import QIcon, QImage, QPixmap
# from PyQt5.QtCore import Qt
# import os
# import cv2
# import json


# Logging configuration
logging.basicConfig(level=logging.CRITICAL+1, format='%(asctime)s %(levelname)s:%(message)s')
logger = logging.getLogger(__name__)


class AdminPanel(QMainWindow):
    def __init__(self):
        super().__init__()
        self.logger = Logger()
        # set_admin_only_access(get_run_path())
        if not is_admin():
            critical_error(logger)
        self.setWindowTitle("Admin Panel")
        self.setGeometry(50, 50, 1200, 600)
        self.setMinimumSize(1500, 950)  # Minimum size for convenience
        self.config = Config()
        self.cameras = []
        self.camera = None
        
        self.theme_manager = ThemeManager()
        
        self.init_ui()
        self.apply_config_settings()
        
    def init_ui(self) -> None:
        """Initialize the user interface."""
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Initialize settings tab via SettingsTab
        self.settings_tab = SettingsTab(self.config, self.theme_manager)
        self.notifications_tab = QWidget()
        self.new_logs_tab = QWidget()

        self.tabs.addTab(self.settings_tab, "Settings")
        self.tabs.addTab(self.new_logs_tab, "Log")

        # Initialize logs tab
        self.new_logs_tab_instance = LogsTab()
        self.new_logs_tab.setLayout(self.new_logs_tab_instance.logs_layout)
        
        # Apply styles for tabs in Material Design 3 style
        theme = self.theme_manager.get_theme()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                background-color: {theme.surface};
                border: none;
            }}
            QTabBar::tab {{
                background-color: {theme.surface};
                color: {theme.on_surface};
                padding: {self.theme_manager.constants.padding_small}px 10px;
                margin-right: 4px;
                border-radius: {self.theme_manager.constants.corner_radius_small}px;
                font-family: {self.theme_manager.typography.font_family};
                font-size: {self.theme_manager.typography.label_medium}px;
                font-weight: {self.theme_manager.typography.font_weight_medium};
                min-height: 32px;
                min-width: 100px;
                max-width: 200px;
                text-align: left;
            }}
            QTabBar::tab:hover {{
                background-color: {theme.primary_container};
                color: {theme.on_surface};
            }}
            QTabBar::tab:selected {{
                background-color: {theme.surface};
                color: {theme.on_surface};
            }}
            QTabBar::tab:!selected {{
                background-color: {theme.primary_container};
                color: {theme.on_surface};
                border-bottom: 2px solid {theme.primary};
            }}
        """)
        # self.tabs.setStyleSheet(f"""
        #     QTabWidget::pane {{
        #         background-color: {theme.surface};
        #         border: none;
        #     }}
        #     QTabBar::tab {{
        #         background-color: {theme.surface};
        #         color: {theme.on_surface};
        #         padding: {self.theme_manager.constants.padding_small}px 10px;
        #         margin-right: 4px;
        #         border-radius: {self.theme_manager.constants.corner_radius_small}px;
        #         font-family: {self.theme_manager.typography.font_family};
        #         font-size: {self.theme_manager.typography.label_medium}px;
        #         font-weight: {self.theme_manager.typography.font_weight_medium};
        #         min-height: 32px;
        #         min-width: 100px;
        #         max-width: 200px;
        #         text-align: left;
        #     }}
        #     QTabBar::tab:hover {{
        #         background-color: {theme.primary_container};
        #         color: {theme.on_surface};
        #     }}
        #     QTabBar::tab:selected {{
        #         background-color: {theme.primary_container};
        #         color: {theme.on_surface};
        #         border-bottom: 2px solid {theme.primary};
        #     }}
        #     QTabBar::tab:!selected {{
        #         background-color: {theme.surface};
        #         color: {theme.on_surface};
        #     }}
        # """)
        
    def apply_config_settings(self) -> None:
        if self.config.get("autostart")["on_system_start"]:
            enable_autostart(APP_NAME, get_project_main_path())
        else:
            disable_autostart(APP_NAME)

    def toggle_theme(self):
        """Toggle between light and dark themes."""
        self.current_theme = "dark" if self.current_theme == "light" else "light"
        self.logs_tab.switch_theme(self.current_theme)


def run_admin_panel():
    app = QApplication(sys.argv)
    window = AdminPanel()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    run_admin_panel()