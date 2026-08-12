from PySide6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QListWidget, 
                             QHBoxLayout, QPushButton, QLineEdit)
from PySide6.QtCore import Qt
from src.ui.style import RED_STYLE
from src.ui.custom_title_bar import CustomTitleBar

class ProcessManagerDialog(QDialog):
    """Диалоговое окно управления списками приложений."""

    def __init__(self, processes: list, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.resize(360, 440)
        self.setStyleSheet(RED_STYLE)
        self.processes = list(processes)

        root_widget = QWidget(self)
        root_widget.setObjectName("RootWidget")

        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.addWidget(root_widget)

        main_layout = QVBoxLayout(root_widget)
        main_layout.setContentsMargins(0, 0, 0, 16)

        # Кастомная шапка
        self.title_bar = CustomTitleBar(self, title="Раздельное туннелирование")
        main_layout.addWidget(self.title_bar)

        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(16, 12, 16, 0)
        content_layout.setSpacing(12)

        self.list_widget = QListWidget(self)
        self.list_widget.addItems(self.processes)
        content_layout.addWidget(self.list_widget)

        self.input_field = QLineEdit(self)
        self.input_field.setPlaceholderText("Имя файла (напр. example.exe)")
        content_layout.addWidget(self.input_field)

        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("Добавить", self)
        self.btn_add.clicked.connect(self.add_process)

        self.btn_remove = QPushButton("Удалить", self)
        self.btn_remove.clicked.connect(self.remove_process)

        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_remove)
        content_layout.addLayout(btn_layout)

        self.btn_save = QPushButton("Готово", self)
        self.btn_save.clicked.connect(self.accept)
        content_layout.addWidget(self.btn_save)

        main_layout.addLayout(content_layout)

    def add_process(self):
        text = self.input_field.text().strip()
        if text:
            # Автоматически добавляем .exe, если пользователь забыл
            if not text.lower().endswith(".exe"):
                text += ".exe"
                
            if text not in self.processes:
                self.processes.append(text)
                self.list_widget.addItem(text)
                self.input_field.clear()

    def remove_process(self):
        current = self.list_widget.currentItem()
        if current:
            val = current.text()
            self.processes.remove(val)
            self.list_widget.takeItem(self.list_widget.row(current))

    def get_processes(self) -> list:
        return self.processes