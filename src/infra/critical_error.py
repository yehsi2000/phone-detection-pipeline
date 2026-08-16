from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import Qt
import sys


message = """
Application started without administrator privileges!
Please contact your administrator or run the application using their credentials.
"""

def critical_error(logger):
    msg = QMessageBox()
    msg.setWindowFlags(Qt.WindowStaysOnTopHint)
    msg.setWindowTitle("Critical error")
    msg.setText(message)
    msg.setStandardButtons(QMessageBox.Ok)
    msg.exec_()
    logger.debug(f"Showed alert: {message}")
    sys.exit()
