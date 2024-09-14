from PyQt5.QtWidgets import QDialog, QPushButton, QVBoxLayout, QHBoxLayout, QLabel, QDesktopWidget

class HotkeyDialog(QDialog):
    def __init__(self, current_hotkey="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Assign Hotkey")

        screen_size = QDesktopWidget().screenGeometry()
        self.resize(int(screen_size.width() * 0.3), int(screen_size.height() * 0.2))

        self.layout = QVBoxLayout()
        self.layout.setSpacing(20)

        self.hotkey_label = QLabel('Press the desired hotkey combination...')
        self.layout.addWidget(self.hotkey_label)

        button_layout = QHBoxLayout()
        self.reset_button = QPushButton("Reset")
        self.reset_button.clicked.connect(self.reset_hotkey)
        self.confirm_button = QPushButton("Confirm")
        self.confirm_button.clicked.connect(self.accept)
        button_layout.addWidget(self.reset_button)
        button_layout.addWidget(self.confirm_button)

        self.layout.addLayout(button_layout)
        self.setLayout(self.layout)

        self.current_hotkey = set(current_hotkey.split('+')) if current_hotkey else set()
        self.update_hotkey_label()

    def reset_hotkey(self):
        self.current_hotkey.clear()
        self.update_hotkey_label()

    def update_hotkey_label(self):
        hotkey_str = '+'.join(sorted(self.current_hotkey)) if self.current_hotkey else "No keys pressed"
        self.hotkey_label.setText(f'Current hotkey: {hotkey_str}')
