from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QListWidgetItem

class SoundItem(QListWidgetItem):
    def __init__(self, title, filename, is_favorite=False):
        super().__init__(title)
        self.filename = filename
        self.is_favorite = is_favorite
        self.update_icon()

    def update_icon(self):
        if self.is_favorite:
            self.setIcon(QIcon('star.png'))
        else:
            self.setIcon(QIcon())