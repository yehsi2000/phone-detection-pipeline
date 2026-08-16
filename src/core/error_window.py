from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt
import sys

class ErrorWindow:
    def __init__(self):
        self.app = QApplication(sys.argv) if QApplication.instance() is None else QApplication.instance()

    def show_error(self, message):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setText(message)
        msg.setWindowTitle("Error")
        msg.setStandardButtons(QMessageBox.Ok)
        # Set window on top of everything and full screen
        msg.setWindowFlags(Qt.WindowStaysOnTopHint)
        # Configure style: large font, centered text, red background
        msg.setStyleSheet("QLabel { font-size: 20pt; text-align: center; } QMessageBox { background-color: #ffcccc; }")
        msg.showFullScreen()
        msg.exec_()