from PyQt5.QtWidgets import QDialog, QListWidget, QVBoxLayout, QPushButton, QSizePolicy, QDesktopWidget

class SoundSelector(QDialog):
    def __init__(self, sound_list, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Select Sound')

        screen_size = QDesktopWidget().screenGeometry()
        self.resize(int(screen_size.width() * 0.3), int(screen_size.height() * 0.2))

        self.layout = QVBoxLayout()
        self.layout.setSpacing(20)

        self.sound_list = QListWidget()
        self.sound_list.addItems(sound_list)
        self.layout.addWidget(self.sound_list)

        self.select_button = QPushButton('Play Selected')
        self.layout.addWidget(self.select_button)
        self.select_button.clicked.connect(self.accept)

        self.setLayout(self.layout)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
