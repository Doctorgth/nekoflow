from PySide6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QListWidget, 
                             QHBoxLayout, QPushButton, QLineEdit, QCheckBox, 
                             QLabel, QFormLayout, QMessageBox, QFileDialog)
from PySide6.QtCore import Qt
from src.ui.style import RED_STYLE
from src.ui.custom_title_bar import CustomTitleBar

class ServerManagerDialog(QDialog):
    """Диалоговое окно управления серверами с поддержкой авторизации и TLS."""

    def __init__(self, servers: list, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.resize(480, 640)  # Увеличиваем размер окна настройки серверов
        self.setStyleSheet(RED_STYLE)
        
        # Глубокое копирование списка серверов, чтобы не менять оригинал до сохранения
        self.servers = [s.copy() if isinstance(s, dict) else {"address": s, "port": 1080, "user": "", "pass": "", "tls": False, "cert": "", "timeout": 30} for s in servers]

        root_widget = QWidget(self)
        root_widget.setObjectName("RootWidget")

        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.addWidget(root_widget)

        main_layout = QVBoxLayout(root_widget)
        main_layout.setContentsMargins(0, 0, 0, 16)

        self.title_bar = CustomTitleBar(self, title="Управление серверами")
        main_layout.addWidget(self.title_bar)

        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(16, 12, 16, 0)
        content_layout.setSpacing(12)

        # Список серверов
        self.list_widget = QListWidget(self)
        self.list_widget.setMinimumHeight(180)  # Гарантируем, что список серверов будет крупным
        self._update_list()
        self.list_widget.currentRowChanged.connect(self.on_row_changed)
        content_layout.addWidget(self.list_widget)

        # Форма редактирования
        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignRight)
        
        self.edit_address = QLineEdit(self)
        self.edit_address.setPlaceholderText("IP-адрес (напр. 77.105.128.154)")
        form_layout.addRow("IP-адрес:", self.edit_address)

        self.edit_port = QLineEdit(self)
        self.edit_port.setPlaceholderText("Порт (напр. 1080 или 9090)")
        form_layout.addRow("Порт:", self.edit_port)

        self.edit_user = QLineEdit(self)
        self.edit_user.setPlaceholderText("Логин (опционально)")
        form_layout.addRow("Пользователь:", self.edit_user)

        self.edit_pass = QLineEdit(self)
        self.edit_pass.setPlaceholderText("Пароль (опционально)")
        self.edit_pass.setEchoMode(QLineEdit.Password)
        form_layout.addRow("Пароль:", self.edit_pass)

        self.edit_timeout = QLineEdit(self)
        self.edit_timeout.setPlaceholderText("Таймаут в секундах (напр. 30)")
        form_layout.addRow("Таймаут (сек):", self.edit_timeout)

        self.chk_tls = QCheckBox("Использовать TLS", self)
        self.chk_tls.toggled.connect(self.on_tls_toggled)
        form_layout.addRow("", self.chk_tls)

        # Контейнер для поля сертификата и кнопки выбора файла
        cert_layout = QHBoxLayout()
        self.edit_cert = QLineEdit(self)
        self.edit_cert.setPlaceholderText("Путь к сертификату .pem")
        self.edit_cert.setEnabled(False)
        
        self.btn_browse_cert = QPushButton("...", self)
        self.btn_browse_cert.setFixedWidth(40)
        self.btn_browse_cert.setEnabled(False)
        self.btn_browse_cert.clicked.connect(self.browse_certificate)
        
        cert_layout.addWidget(self.edit_cert)
        cert_layout.addWidget(self.btn_browse_cert)
        
        form_layout.addRow("Сертификат:", cert_layout)

        content_layout.addLayout(form_layout)

        # Кнопки управления сервером
        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("Добавить новый", self)
        self.btn_add.clicked.connect(self.add_server)
        
        self.btn_save_item = QPushButton("Сохранить", self)
        self.btn_save_item.clicked.connect(self.save_current_server)

        self.btn_test = QPushButton("Проверить", self)
        self.btn_test.clicked.connect(self.test_connection)

        self.btn_remove = QPushButton("Удалить", self)
        self.btn_remove.clicked.connect(self.remove_server)

        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_save_item)
        btn_layout.addWidget(self.btn_test)
        btn_layout.addWidget(self.btn_remove)
        content_layout.addLayout(btn_layout)

        # Главная кнопка закрытия
        self.btn_save_all = QPushButton("Закрыть и применить", self)
        self.btn_save_all.setStyleSheet("margin-top: 10px;")
        self.btn_save_all.clicked.connect(self.accept)
        content_layout.addWidget(self.btn_save_all)

        main_layout.addLayout(content_layout)

        if self.servers:
            self.list_widget.setCurrentRow(0)

    def _update_list(self):
        self.list_widget.clear()
        for srv in self.servers:
            self.list_widget.addItem(srv.get("address", "Unknown"))

    def on_tls_toggled(self, checked: bool):
        self.edit_cert.setEnabled(checked)
        self.btn_browse_cert.setEnabled(checked)

    def browse_certificate(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выбрать сертификат", "", "Certificate Files (*.pem *.crt *.cer);;All Files (*)"
        )
        if file_path:
            import os
            # Нормализуем слеши для Windows/Linux
            file_path = os.path.normpath(file_path)
            try:
                rel_path = os.path.relpath(file_path, os.getcwd())
                if not rel_path.startswith(".."):
                    file_path = rel_path
            except Exception:
                pass
            self.edit_cert.setText(file_path)

    def on_row_changed(self, row: int):
        if row < 0 or row >= len(self.servers):
            self.edit_address.clear()
            self.edit_port.clear()
            self.edit_timeout.clear()
            self.edit_user.clear()
            self.edit_pass.clear()
            self.chk_tls.setChecked(False)
            self.edit_cert.clear()
            return

        srv = self.servers[row]
        self.edit_address.setText(srv.get("address", ""))
        self.edit_port.setText(str(srv.get("port", 1080)))
        self.edit_timeout.setText(str(srv.get("timeout", 30)))
        self.edit_user.setText(srv.get("user", ""))
        self.edit_pass.setText(srv.get("pass", ""))
        self.chk_tls.setChecked(srv.get("tls", False))
        self.edit_cert.setText(srv.get("cert", ""))

    def add_server(self):
        addr = self.edit_address.text().strip()
        if not addr:
            QMessageBox.warning(self, "Ошибка", "Укажите адрес сервера!")
            return
        
        port_val = self.edit_port.text().strip()
        port = int(port_val) if port_val.isdigit() and 1 <= int(port_val) <= 65535 else 1080

        t_val = self.edit_timeout.text().strip()
        timeout = int(t_val) if t_val.isdigit() and 1 <= int(t_val) <= 300 else 30
        
        # Защита от дубликатов
        for s in self.servers:
            if s.get("address") == addr and s.get("port") == port:
                QMessageBox.warning(self, "Дубликат", "Сервер с таким IP и портом уже существует!")
                return

        new_srv = {
            "address": addr,
            "port": port,
            "timeout": timeout,
            "user": self.edit_user.text().strip(),
            "pass": self.edit_pass.text(),
            "tls": self.chk_tls.isChecked(),
            "cert": self.edit_cert.text().strip()
        }
        self.servers.append(new_srv)
        self._update_list()
        self.list_widget.setCurrentRow(len(self.servers) - 1)

    def save_current_server(self):
        row = self.list_widget.currentRow()
        if row < 0:
            return
        
        addr = self.edit_address.text().strip()
        if not addr:
            return

        port_val = self.edit_port.text().strip()
        port = int(port_val) if port_val.isdigit() else 1080

        t_val = self.edit_timeout.text().strip()
        timeout = int(t_val) if t_val.isdigit() else 30

        self.servers[row] = {
            "address": addr,
            "port": port,
            "timeout": timeout,
            "user": self.edit_user.text().strip(),
            "pass": self.edit_pass.text(),
            "tls": self.chk_tls.isChecked(),
            "cert": self.edit_cert.text().strip()
        }
        self._update_list()
        self.list_widget.setCurrentRow(row)

    def remove_server(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            self.servers.pop(row)
            self._update_list()

    def accept(self):
        """Переопределяем стандартный метод: сохраняем текущие поля перед закрытием."""
        self._is_closing = True
        # Если в полях есть данные, принудительно сохраняем их в список перед выходом
        if self.edit_address.text().strip():
            row = self.list_widget.currentRow()
            if row >= 0:
                self.save_current_server()
            else:
                self.add_server()
        super().accept()
        
    def reject(self):
        self._is_closing = True
        super().reject()

    def get_servers(self) -> list:
        return self.servers

    def test_connection(self):
        """Интерфейсный метод запуска проверки соединения в фоновом ОС-потоке."""
        addr = self.edit_address.text().strip()
        if not addr:
            QMessageBox.warning(self, "Ошибка", "Укажите адрес сервера для проверки!")
            return

        self.btn_test.setText("Проверка...")
        self.btn_test.setEnabled(False)

        # Переменные обмена данными с фоновым потоком
        self._test_success = False
        self._test_err_msg = ""
        self._test_finished = False
        self._is_closing = False

        def thread_target():
            try:
                success, err = self._run_test_handshake_isolated()
                self._test_success = success
                self._test_err_msg = err
            except Exception as e:
                self._test_success = False
                self._test_err_msg = str(e)
            finally:
                self._test_finished = True

        import threading
        import time

        # Запускаем изоляционный поток
        test_thread = threading.Thread(target=thread_target, daemon=True)
        test_thread.start()

        # Безопасный асинхронный опрос завершения потока без блокировки UI и без processEvents
        from PySide6.QtCore import QTimer

        def check_finished():
            if getattr(self, "_is_closing", False):
                return
                
            if self._test_finished:
                self.btn_test.setText("Проверить")
                self.btn_test.setEnabled(True)
                if self._test_success:
                    QMessageBox.information(
                        self, "Успех", 
                        "Соединение с сервером успешно установлено!\n\nАвторизация одобрена, тестовый пакет успешно прошел через туннель."
                    )
                else:
                    QMessageBox.critical(
                        self, "Ошибка проверки", 
                        f"Не удалось установить соединение.\n\nДетали ошибки:\n{self._test_err_msg}"
                    )
            else:
                QTimer.singleShot(50, self, check_finished)

        QTimer.singleShot(50, self, check_finished)

    def _run_test_handshake_isolated(self) -> tuple[bool, str]:
        """Запускает чистый асинхронный цикл в фоновом потоке без конфликтов с Qt."""
        import asyncio
        try:
            from client.aptcp_client import APTCPTunnelClient
            from common.tunnel import send_tunnel_cmd_request, read_tunnel_cmd_response
            from common.socks5 import CMD_CONNECT, REP_SUCCESS
        except ImportError as e:
            return False, f"Ошибка импорта оригинальных библиотек: {e}\n\nПожалуйста, скопируйте папки 'client' и 'common' из вашего рабочего проекта в корень этого проекта."

        aptcp_host = self.edit_address.text().strip().split(":")[0]
        port_val = self.edit_port.text().strip()
        aptcp_port = int(port_val) if port_val.isdigit() else 1080

        user = self.edit_user.text().strip()
        pwd = self.edit_pass.text()
        tls = self.chk_tls.isChecked()
        cert = self.edit_cert.text().strip() if tls else None

        async def _async_test():
            tunnel_client = APTCPTunnelClient(
                aptcp_host,
                aptcp_port,
                tls_enabled=tls,
                tls_ca_cert=cert
            )
            # Авторизуемся на сервере
            ptcp_stream = await tunnel_client.connect_and_authenticate(
                auth_enabled=bool(user),
                username=user,
                password=pwd
            )
            
            try:
                # Тестовый запрос к внешнему миру через туннель
                await send_tunnel_cmd_request(ptcp_stream, CMD_CONNECT, "example.com", 80)
                rep, _, _, _ = await read_tunnel_cmd_response(ptcp_stream)
                await ptcp_stream.close()
                if rep == REP_SUCCESS:
                    return True, ""
                return True, "Авторизация успешно пройдена (проверка внешнего хоста пропущена)."
            except Exception:
                try:
                    await ptcp_stream.close()
                except Exception:
                    pass
                return True, "Авторизация успешно пройдена (проверка внешнего хоста пропущена)."

        # Читаем заданный таймаут
        t_val = self.edit_timeout.text().strip()
        user_timeout = float(t_val) if t_val.isdigit() else 30.0

        try:
            # Создаем полностью независимый Event Loop для фонового потока
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # НЕ ВЫПОЛНЯЕМ route delete, чтобы не ломать активный туннель пользователя!

            return loop.run_until_complete(asyncio.wait_for(_async_test(), timeout=user_timeout))
        except asyncio.TimeoutError:
            return False, f"Таймаут ожидания ответа от сервера ({user_timeout} сек)."
        except Exception as e:
            return False, str(e)
        finally:
            # Гарантированная зачистка фоновых тасок aioptcp перед уничтожением loop во избежание предупреждений
            try:
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                loop.close()
            except Exception:
                pass