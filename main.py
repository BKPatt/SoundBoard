import os
import sys
from PyQt5.QtWidgets import QApplication
from SoundPlayer import SoundPlayer
from PyQt5.QtGui import QColor, QPalette, QIcon
from PyQt5.QtCore import Qt

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.Window, QColor(44, 62, 80))
    dark_palette.setColor(QPalette.WindowText, Qt.white)
    dark_palette.setColor(QPalette.Base, QColor(52, 73, 94))
    dark_palette.setColor(QPalette.AlternateBase, QColor(44, 62, 80))
    dark_palette.setColor(QPalette.ToolTipBase, Qt.white)
    dark_palette.setColor(QPalette.ToolTipText, Qt.white)
    dark_palette.setColor(QPalette.Text, Qt.white)
    dark_palette.setColor(QPalette.Button, QColor(52, 152, 219))
    dark_palette.setColor(QPalette.ButtonText, Qt.white)
    dark_palette.setColor(QPalette.BrightText, Qt.red)
    dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(dark_palette)
    
    icon_path = os.path.join(os.path.dirname(__file__), 'virt_soundboard.png')
    app.setWindowIcon(QIcon(icon_path))
    
    player = SoundPlayer()
    player.show()
    sys.exit(app.exec_())