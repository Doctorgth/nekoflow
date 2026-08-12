# Стилистика RED_STYLE - Dark Graphite / Crimson Red
RED_STYLE = """
/* Главное окно и прозрачность */
QWidget#RootWidget {
    background-color: rgba(12, 12, 16, 0.96);
    border: 1px solid rgba(255, 0, 51, 0.6);
    border-radius: 10px;
}

QWidget {
    color: #e0e0e0;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}

/* Диалоговые окна */
QDialog {
    background-color: transparent;
}

/* Кастомный заголовок */
#TitleBar {
    background-color: #16161e;
    border-bottom: 1px solid #e60026;
    border-top-left-radius: 9px;
    border-top-right-radius: 9px;
}

#TitleLabel {
    font-weight: 700;
    font-size: 13px;
    color: #ff1a40;
    letter-spacing: 0.5px;
}

#CloseButton, #MinimizeButton {
    background-color: transparent;
    border: none;
    font-size: 13px;
    font-weight: bold;
    color: #888899;
}

#CloseButton:hover {
    background-color: #ff0033;
    color: white;
    border-top-right-radius: 9px;
}

#MinimizeButton:hover {
    background-color: #252530;
    color: white;
}

/* Карточки-контейнеры */
#MainCard {
    background-color: #14141c;
    border: 1px solid rgba(255, 0, 51, 0.35);
    border-radius: 8px;
    padding: 12px;
}

/* Радио-кнопки (Чистая красная обводка без заполнения при выборе) */
QRadioButton {
    color: #d0d0d8;
    font-size: 13px;
    font-weight: 600;
    padding: 4px;
    spacing: 10px;
}

QRadioButton::indicator {
    width: 14px;
    height: 14px;
    border-radius: 8px;
}

QRadioButton::indicator:unchecked {
    border: 2px solid #444458;
    background-color: #0c0c10;
}

QRadioButton::indicator:unchecked:hover {
    border: 2px solid #888899;
}

QRadioButton::indicator:checked {
    border: 2px solid #ff0033;
    background-color: #0c0c10;
}

QRadioButton::indicator:checked:hover {
    border: 2px solid #ff3355;
}

/* Чекбоксы */
QCheckBox {
    color: #d0d0d8;
    font-weight: 600;
    padding: 4px;
    spacing: 10px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 8px;
}

QCheckBox::indicator:unchecked {
    border: 2px solid #444458;
    background-color: #0d0d12;
    background: none;
    image: none;
}

QCheckBox::indicator:unchecked:hover {
    border: 2px solid #666677;
    background-color: #0d0d12;
    background: none;
    image: none;
}

QCheckBox::indicator:checked {
    border: 2px solid #ff0033;
    background-color: #0d0d12;
    background: qradialgradient(cx:0.5, cy:0.5, radius:0.35, fx:0.5, fy:0.5, stop:0 #ff0033, stop:0.7 #ff0033, stop:0.75 #0d0d12, stop:1.0 #0d0d12);
    image: url("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAAAAXNSR0IArs4c6QAAAAlwSFlzAAALEwAACxMBAJqcGAAAAGdJREFUOBFjYBxaQJpB/v8fIG4C4pNA3A/E4UA8CIgnkGAAMv4/P3++A8S/ofgEEf6A1IAsiDEw4MB/Egz89++fAazgHQMOUKQAxI0fP37EAIqNg3aQARi2xPifBAyMNXz69OmDJAOIMgC3HUP3dYy+bAAAAABJRU5ErkJggg==");
}

QCheckBox::indicator:checked:hover {
    border: 2px solid #ff3355;
}

/* Выпадающий список (QComboBox) */
#ServerSelector {
    background-color: #0e0e14;
    border: 1px solid rgba(255, 0, 51, 0.5);
    border-radius: 6px;
    padding: 8px 12px;
    font-weight: bold;
    color: #ff3355;
}

#ServerSelector:hover {
    background-color: #14141d;
    border: 1px solid #ff0033;
}

#ServerSelector QAbstractItemView {
    background-color: #121218;
    border: 1px solid #ff0033;
    selection-background-color: #e60026;
    selection-color: #ffffff;
    padding: 5px;
}

/* Поля ввода (QLineEdit) */
QLineEdit {
    background-color: #0e0e14;
    border: 1px solid rgba(255, 0, 51, 0.4);
    border-radius: 6px;
    padding: 8px 12px;
    color: #ffffff;
    selection-background-color: #e60026;
}

QLineEdit:focus {
    border: 1px solid #ff0033;
}

/* Списки (QListWidget) */
QListWidget {
    background-color: #0e0e14;
    border: 1px solid rgba(255, 0, 51, 0.4);
    border-radius: 6px;
    color: #ffffff;
    padding: 4px;
}

QListWidget::item {
    padding: 6px;
    border-radius: 4px;
}

QListWidget::item:selected {
    background-color: #e60026;
    color: #ffffff;
}

/* Кнопки управления */
QPushButton {
    background-color: rgba(35, 35, 45, 0.9);
    color: #ffffff;
    border: 1px solid rgba(255, 0, 51, 0.5);
    border-radius: 6px;
    padding: 8px 14px;
    font-weight: 700;
    letter-spacing: 0.3px;
}

QPushButton:hover {
    background-color: #ff0033;
    color: #ffffff;
    border: 1px solid #ff3355;
}

QPushButton:pressed {
    background-color: #b3001b;
}

QPushButton:disabled {
    background-color: rgba(20, 20, 25, 0.4);
    border: 1px solid #333344;
    color: #555566;
}
"""