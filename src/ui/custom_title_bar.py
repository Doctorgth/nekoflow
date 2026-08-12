from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt

class CustomTitleBar(QWidget):
    """Кастомная шапка окна NekoFlow с кнопками и перетаскиванием."""

    def __init__(self, parent=None, title: str = "NekoFlow"):
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self.setFixedHeight(38)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 0, 0)

        self.title_label = QLabel(title, self)
        self.title_label.setObjectName("TitleLabel")
        layout.addWidget(self.title_label)

        layout.addStretch()

        self.btn_minimize = QPushButton("—", self)
        self.btn_minimize.setObjectName("MinimizeButton")
        self.btn_minimize.setFixedSize(38, 38)
        self.btn_minimize.clicked.connect(self._minimize_window)

        self.btn_close = QPushButton("✕", self)
        self.btn_close.setObjectName("CloseButton")
        self.btn_close.setFixedSize(38, 38)
        self.btn_close.clicked.connect(self._close_window)

        layout.addWidget(self.btn_minimize)
        layout.addWidget(self.btn_close)

    def _minimize_window(self):
        win = self.window()
        if win:
            win.showMinimized()

    def _close_window(self):
        win = self.window()
        if win:
            win.close()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            win = self.window()
            if win and win.windowHandle():
                win.windowHandle().startSystemMove()
            event.accept()