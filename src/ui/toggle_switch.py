from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QPropertyAnimation, Property, Signal
from PySide6.QtGui import QPainter, QColor, QPaintEvent

class QToggleSwitch(QWidget):
    """Плавный переключатель Лево/Право (Вкл/Выкл) в стилистике Братства НОД."""

    toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(60, 30)
        self._checked = False
        self._circle_position = 3.0

        self._anim = QPropertyAnimation(self, b"circle_position", self)
        self._anim.setDuration(180)

    @Property(float)
    def circle_position(self) -> float:
        return self._circle_position

    @circle_position.setter
    def circle_position(self, pos: float):
        self._circle_position = pos
        self.update()

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool):
        if self._checked != checked:
            self._checked = checked
            self._animate(checked)
            self.toggled.emit(self._checked)

    def _animate(self, checked: bool):
        self._anim.stop()
        self._anim.setStartValue(self._circle_position)
        self._anim.setEndValue(33.0 if checked else 3.0)
        self._anim.start()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setChecked(not self._checked)

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Неоновый трек (Включен - Красный, Выключен - Темно-серый)
        bg_color = QColor("#ff0033") if self._checked else QColor("#1c1c26")
        border_pen = QColor("#ff3355") if self._checked else QColor("#3a3a4c")

        painter.setBrush(bg_color)
        painter.setPen(border_pen)
        painter.drawRoundedRect(0, 0, self.width() - 1, self.height() - 1, 15, 15)

        # Бегунок (Включен - Белый, Выключен - Стальной)
        circle_color = QColor("#ffffff") if self._checked else QColor("#888899")
        painter.setPen(Qt.NoPen)
        painter.setBrush(circle_color)
        painter.drawEllipse(int(self._circle_position), 3, 24, 24)