from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QRadioButton, QButtonGroup, QLabel, QPushButton, 
                             QCheckBox, QComboBox, QMessageBox)
from PySide6.QtCore import Qt, QThread, Signal

from src.config import ConfigManager
from src.ui.style import RED_STYLE
from src.ui.custom_title_bar import CustomTitleBar
from src.ui.toggle_switch import QToggleSwitch
from src.ui.server_dialog import ServerManagerDialog
from src.ui.process_dialog import ProcessManagerDialog

class ConnectWorker(QThread):
    """Фоновый воркер для асинхронного запуска сетевых движков без блокировки интерфейса."""
    finished = Signal(bool, str)

    def __init__(self, engine):
        super().__init__()
        self.engine = engine

    def run(self):
        try:
            success = self.engine.start()
            if success:
                self.finished.emit(True, "")
            else:
                self.finished.emit(False, "Не удалось инициализировать сетевой интерфейс.")
        except Exception as e:
            self.finished.emit(False, str(e))

class DisconnectWorker(QThread):
    """Фоновый воркер для асинхронной остановки сетевых движков без блокировки интерфейса."""
    finished = Signal()

    def __init__(self, engine):
        super().__init__()
        self.engine = engine

    def run(self):
        try:
            if self.engine:
                self.engine.stop()
        except Exception as e:
            print(f"[Connecter] Ошибка при фоновой остановке движка: {e}")
        finally:
            self.finished.emit()

class MainWindow(QMainWindow):
    """Главный UI контейнер программы Connecter."""

    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config = config_manager
        
        # Включаем настоящую прозрачность окна
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setMinimumSize(360, 560)
        self.resize(360, 560)
        self.setStyleSheet(RED_STYLE)
        self.setWindowTitle("NekoFlow")

        # Инициализация сетевых движков
        self.engines = {}
        self.active_engine = None
        self._connect_worker = None
        self._disconnect_worker = None

        self._init_ui()
        self._load_config_to_ui()
        self._setup_window_and_tray_icon()

    def _init_ui(self):
        # Корневой контейнер с закруглением и полупрозрачным фоном
        root_widget = QWidget(self)
        root_widget.setObjectName("RootWidget")
        self.setCentralWidget(root_widget)

        main_layout = QVBoxLayout(root_widget)
        main_layout.setContentsMargins(0, 0, 0, 16)

        # Кастомная шапка NekoFlow
        self.title_bar = CustomTitleBar(self, title="NekoFlow")
        main_layout.addWidget(self.title_bar)

        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(16, 12, 16, 0)
        content_layout.setSpacing(14)

        # 1. Переключатель Лево/Право (Вкл/Выкл)
        toggle_layout = QHBoxLayout()
        toggle_layout.setContentsMargins(4, 0, 4, 0)
        self.status_label = QLabel("ОТКЛЮЧЕНО", self)
        self.status_label.setStyleSheet("font-weight: bold; font-size: 15px; color: #a0a0b2; letter-spacing: 1px;")
        
        self.toggle_btn = QToggleSwitch(self)
        self.toggle_btn.toggled.connect(self.on_toggle_connect)

        toggle_layout.addWidget(self.status_label)
        toggle_layout.addStretch()
        toggle_layout.addWidget(self.toggle_btn)
        content_layout.addLayout(toggle_layout)

        # 2. Выбор режима (TUN / WinDivert / SOCKS)
        mode_card = QWidget(self)
        mode_card.setObjectName("MainCard")
        mode_layout = QVBoxLayout(mode_card)

        mode_title = QLabel("Режим перехвата:", mode_card)
        mode_title.setStyleSheet("font-weight: bold; color: #ff1a40;")
        mode_layout.addWidget(mode_title)

        self.mode_group = QButtonGroup(self)
        self.radio_tun = QRadioButton("TUN Mode", mode_card)
        self.radio_socks = QRadioButton("SOCKS Proxy", mode_card)

        self.mode_group.addButton(self.radio_tun, 1)
        self.mode_group.addButton(self.radio_socks, 2)

        mode_layout.addWidget(self.radio_tun)
        mode_layout.addWidget(self.radio_socks)

        self.mode_group.idClicked.connect(self.on_mode_changed)
        content_layout.addWidget(mode_card)

        # 3. Раздельное туннелирование
        split_card = QWidget(self)
        split_card.setObjectName("MainCard")
        split_layout = QVBoxLayout(split_card)

        self.chk_split = QCheckBox("Раздельное туннелирование", split_card)
        self.chk_split.toggled.connect(self.on_split_toggled)
        split_layout.addWidget(self.chk_split)

        self.btn_edit_apps = QPushButton("Список приложений...", split_card)
        self.btn_edit_apps.clicked.connect(self.open_process_dialog)
        split_layout.addWidget(self.btn_edit_apps)

        content_layout.addWidget(split_card)

        # 4. Выбор сервера
        server_card = QWidget(self)
        server_card.setObjectName("MainCard")
        server_layout = QVBoxLayout(server_card)

        server_title = QLabel("Текущий сервер:", server_card)
        server_title.setStyleSheet("font-weight: bold; color: #ff1a40;")
        server_layout.addWidget(server_title)

        self.combo_servers = QComboBox(server_card)
        self.combo_servers.setObjectName("ServerSelector")
        self.combo_servers.currentTextChanged.connect(self.on_server_selected)
        server_layout.addWidget(self.combo_servers)

        self.btn_manage_servers = QPushButton("Управление серверами", server_card)
        self.btn_manage_servers.clicked.connect(self.open_server_dialog)
        server_layout.addWidget(self.btn_manage_servers)

        content_layout.addWidget(server_card)

        main_layout.addLayout(content_layout)

    def _load_config_to_ui(self):
        # Нормализация серверов к формату dict
        raw_servers = self.config.get("servers", [])
        servers = []
        for s in raw_servers:
            if isinstance(s, str):
                servers.append({"address": s, "user": "", "pass": "", "tls": False, "cert": ""})
            else:
                servers.append(s)
        self.config.set("servers", servers)

        self.combo_servers.blockSignals(True)
        self.combo_servers.clear()
        for s in servers:
            self.combo_servers.addItem(s.get("address", ""))
            
        selected_srv = self.config.get("selected_server", "")
        if selected_srv:
            self.combo_servers.setCurrentText(selected_srv)
        self.combo_servers.blockSignals(False)

        # Режим
        mode = self.config.get("mode", "tun")
        if mode == "socks":
            self.radio_socks.setChecked(True)
        else:
            self.radio_tun.setChecked(True)

        # Раздельное туннелирование
        split_enabled = self.config.get("split_tunneling", False)
        self.chk_split.setChecked(split_enabled)

        self._update_split_ui_state()

    def _update_split_ui_state(self):
        is_socks = self.radio_socks.isChecked()
        if is_socks:
            self.chk_split.setEnabled(False)
            self.btn_edit_apps.setEnabled(False)
            self.chk_split.setText("Раздельное (недоступно)")
        else:
            self.chk_split.setEnabled(True)
            self.btn_edit_apps.setEnabled(self.chk_split.isChecked())
            self.chk_split.setText("Раздельное туннелирование")

    def on_mode_changed(self, id: int):
        mode_map = {1: "tun", 2: "socks"}
        mode = mode_map.get(id, "tun")
        self.config.set("mode", mode)
        self._update_split_ui_state()

    def on_split_toggled(self, checked: bool):
        self.config.set("split_tunneling", checked)
        self.btn_edit_apps.setEnabled(checked)

    def on_server_selected(self, text: str):
        self.config.set("selected_server", text)

    def open_server_dialog(self):
        servers = self.config.get("servers", [])
        dialog = ServerManagerDialog(servers, self)
        if dialog.exec():
            new_servers = dialog.get_servers()
            self.config.set("servers", new_servers)
            
            self.combo_servers.blockSignals(True)
            self.combo_servers.clear()
            for s in new_servers:
                self.combo_servers.addItem(s.get("address", ""))
            
            # Восстанавливаем выбор (если старого адреса нет, берем первый доступный)
            selected = self.config.get("selected_server", "")
            if self.combo_servers.findText(selected) == -1 and self.combo_servers.count() > 0:
                selected = self.combo_servers.itemText(0)
                self.config.set("selected_server", selected)
            
            self.combo_servers.setCurrentText(selected)
            self.combo_servers.blockSignals(False)

    def open_process_dialog(self):
        processes = self.config.get("process_whitelist", [])
        dialog = ProcessManagerDialog(processes, self)
        if dialog.exec():
            new_procs = dialog.get_processes()
            self.config.set("process_whitelist", new_procs)

    def on_toggle_connect(self, checked: bool):
        # Блокируем множественные быстрые нажатия
        if not self.toggle_btn.isEnabled():
            return

        if checked:
            mode = self.config.get("mode", "tun")
            
            # Ленивая инициализация движков: импортируем и создаем только по требованию
            if mode not in self.engines:
                try:
                    if mode == "tun":
                        from src.network.tun_engine import TunEngine
                        self.engines["tun"] = TunEngine()
                    else:
                        from src.network.socks_engine import SocksEngine
                        self.engines["socks"] = SocksEngine()
                except Exception as e:
                    QMessageBox.critical(self, "Ошибка загрузки движка", f"Не удалось загрузить модули {mode.upper()}: {e}")
                    self.toggle_btn.setChecked(False)
                    return

            engine = self.engines[mode]

            # Сохраняем ссылку на подготавливаемый движок
            self._pending_engine = engine

            # Настройка раздельного туннелирования
            split_on = self.config.get("split_tunneling", False) and mode != "socks"
            whitelist = self.config.get("process_whitelist", [])
            engine.configure_split_tunneling(split_on, whitelist)

            # Передаем конфигурацию текущего выбранного сервера строго из UI-списка
            selected_addr = self.combo_servers.currentText().strip()
            self.config.set("selected_server", selected_addr)
            server_config = {}
            for s in self.config.get("servers", []):
                if s.get("address") == selected_addr:
                    server_config = s
                    break

            if hasattr(engine, 'set_target_server'):
                engine.set_target_server(server_config)

            # Переводим UI в режим "Подключение" (желтый цвет, интерфейс блокируется)
            self.status_label.setText("ПОДКЛЮЧЕНИЕ...")
            self.status_label.setStyleSheet("font-weight: bold; font-size: 15px; color: #ffcc00; letter-spacing: 1px;")
            self._set_controls_enabled(False)
            self.toggle_btn.setEnabled(False)  # Блокируем переключатель во время инициализации

            # Запускаем фоновый поток для подключения
            self._connect_worker = ConnectWorker(engine)
            self._connect_worker.finished.connect(lambda success, err: self._on_connect_finished(success, err, engine, mode))
            self._connect_worker.start()
        else:
            if not self.active_engine:
                self.status_label.setText("ОТКЛЮЧЕНО")
                self.status_label.setStyleSheet("font-weight: bold; font-size: 15px; color: #a0a0b2; letter-spacing: 1px;")
                self._set_controls_enabled(True)
                self.toggle_btn.setEnabled(True)
                return

            # Переводим UI в режим "ОТКЛЮЧЕНИЕ..." (желтый цвет, элементы заблокированы)
            self.status_label.setText("ОТКЛЮЧЕНИЕ...")
            self.status_label.setStyleSheet("font-weight: bold; font-size: 15px; color: #ffcc00; letter-spacing: 1px;")
            self._set_controls_enabled(False)
            self.toggle_btn.setEnabled(False)

            engine_to_stop = self.active_engine
            self.active_engine = None

            # Запускаем фоновый поток для безопасного выключения без фризов UI
            self._disconnect_worker = DisconnectWorker(engine_to_stop)
            self._disconnect_worker.finished.connect(self._on_disconnect_finished)
            self._disconnect_worker.start()

    def _on_disconnect_finished(self):
        """Обработчик завершения фоновой операции отключения."""
        self.status_label.setText("ОТКЛЮЧЕНО")
        self.status_label.setStyleSheet("font-weight: bold; font-size: 15px; color: #a0a0b2; letter-spacing: 1px;")
        self._set_controls_enabled(True)
        self.toggle_btn.setEnabled(True)

    def _on_connect_finished(self, success: bool, error_msg: str, engine, mode: str):
        """Обработчик завершения фоновой операции подключения."""
        self.toggle_btn.setEnabled(True)
        
        if success:
            self.active_engine = engine
            if mode == "socks":
                self.status_label.setText("ПОДКЛЮЧЕНО (PORT 3080)")
            else:
                self.status_label.setText("ПОДКЛЮЧЕНО")
                
            self.status_label.setStyleSheet("font-weight: bold; font-size: 15px; color: #ff0033; letter-spacing: 1px;")
            self._set_controls_enabled(False)
        else:
            reason = error_msg if error_msg else "Неизвестная ошибка инициализации драйвера."
            QMessageBox.warning(self, "Ошибка запуска", f"Не удалось запустить режим {mode.upper()}.\n\nПричина: {reason}")
            
            # Сбрасываем переключатель назад во время ошибки без вызова триггеров повторного клика
            self.toggle_btn.blockSignals(True)
            self.toggle_btn.setChecked(False)
            self.toggle_btn.blockSignals(False)
            
            self.status_label.setText("ОТКЛЮЧЕНО")
            self.status_label.setStyleSheet("font-weight: bold; font-size: 15px; color: #a0a0b2; letter-spacing: 1px;")
            self._set_controls_enabled(True)

    def _set_controls_enabled(self, enabled: bool):
        self.radio_tun.setEnabled(enabled)
        self.radio_socks.setEnabled(enabled)
        self.combo_servers.setEnabled(enabled)
        self.btn_manage_servers.setEnabled(enabled)
        if enabled:
            self._update_split_ui_state()
        else:
            self.chk_split.setEnabled(False)
            self.btn_edit_apps.setEnabled(False)

    def _setup_window_and_tray_icon(self):
        """Настройка иконки окна и иконки в системном трее Windows."""
        import os
        from PySide6.QtGui import QIcon
        from PySide6.QtWidgets import QSystemTrayIcon, QMenu

        # Приоритетный поиск файлов иконок (ищем .ico для лучшего качества в трее)
        icon_path = ""
        search_dirs = ["images", "assets"]
        
        # Сначала ищем конкретные файлы по расширению .ico
        for folder in search_dirs:
            if os.path.exists(folder):
                for f in os.listdir(folder):
                    if f.lower().endswith(".ico"):
                        icon_path = os.path.join(folder, f)
                        break
            if icon_path: break

        # Если .ico не найден, ищем bg_nekoflow.png или любой другой
        if not icon_path:
            for folder in search_dirs:
                if os.path.exists(folder):
                    target = os.path.join(folder, "bg_nekoflow.png")
                    if os.path.exists(target):
                        icon_path = target
                        break
        
        if icon_path:
            icon = QIcon(icon_path)
            self.setWindowIcon(icon)

            # Создание иконки в трее возле часов
            self.tray_icon = QSystemTrayIcon(icon, self)
            self.tray_icon.setToolTip("NekoFlow")

            tray_menu = QMenu(self)
            action_show = tray_menu.addAction("Показать / Свернуть")
            action_show.triggered.connect(self._toggle_window_visibility)
            tray_menu.addSeparator()
            action_exit = tray_menu.addAction("Выход")
            action_exit.triggered.connect(self.close)

            self.tray_icon.setContextMenu(tray_menu)
            self.tray_icon.activated.connect(self._on_tray_icon_activated)
            self.tray_icon.show()

    def _toggle_window_visibility(self):
        if self.isVisible() and not self.isMinimized():
            self.hide()
        else:
            self.showNormal()
            self.activateWindow()

    def _on_tray_icon_activated(self, reason):
        from PySide6.QtWidgets import QSystemTrayIcon
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self._toggle_window_visibility()

    def closeEvent(self, event):
        """Гарантированное отключение движков и зачистка ресурсов при закрытии."""
        # 1. Если поток подключения ещё работает — даем ему короткое время завершиться
        if hasattr(self, "_connect_worker") and self._connect_worker and self._connect_worker.isRunning():
            self._connect_worker.wait(1500)

        # 2. Гарантированно останавливаем активный или готовый к запуску движок
        engine_to_stop = self.active_engine or getattr(self, "_pending_engine", None)
        if engine_to_stop:
            try:
                engine_to_stop.stop()
            except Exception as e:
                print(f"[MainWindow] Ошибка при остановке движка при закрытии: {e}")

        self._pending_engine = None
        self.active_engine = None
        event.accept()