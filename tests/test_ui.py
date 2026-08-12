import pytest
import os
from PySide6.QtCore import Qt
from src.config import ConfigManager
from src.ui.main_window import MainWindow
from src.ui.server_dialog import ServerManagerDialog
from src.ui.process_dialog import ProcessManagerDialog

TEST_CONFIG_PATH = "test_ui_config.json"

@pytest.fixture
def app(qtbot, monkeypatch):
    if os.path.exists(TEST_CONFIG_PATH):
        os.remove(TEST_CONFIG_PATH)
    
    cfg = ConfigManager(TEST_CONFIG_PATH)
    window = MainWindow(cfg)
    
    # Создаем фиктивные движки для тестов интерфейса, исключая загрузку реальных DLL/драйверов
    class MockEngine:
        def start(self): return True
        def stop(self): pass
        def configure_split_tunneling(self, *a, **kw): pass
        def set_target_server(self, *a, **kw): pass

    window.engines = {
        "tun": MockEngine(),
        "socks": MockEngine()
    }

    qtbot.addWidget(window)
    yield window
    
    if os.path.exists(TEST_CONFIG_PATH):
        os.remove(TEST_CONFIG_PATH)

def test_ui_initial_state(app):
    assert app.status_label.text() == "ОТКЛЮЧЕНО"
    assert app.radio_tun.isChecked() is True

def test_mode_switch(app):
    app.radio_socks.click()
    assert app.config.get("mode") == "socks"
    assert app.chk_split.isEnabled() is False

def test_toggle_button_connect(app, qtbot):
    qtbot.mouseClick(app.toggle_btn, Qt.LeftButton)
    qtbot.waitUntil(lambda: app.status_label.text().startswith("ПОДКЛЮЧЕНО"), timeout=3000)
    assert app.toggle_btn.isChecked() is True
    assert "ПОДКЛЮЧЕНО" in app.status_label.text()

def test_toggle_button_disconnect(app, qtbot):
    # 1. Включаем
    qtbot.mouseClick(app.toggle_btn, Qt.LeftButton)
    qtbot.waitUntil(lambda: app.status_label.text().startswith("ПОДКЛЮЧЕНО"), timeout=3000)
    assert app.toggle_btn.isChecked() is True

    # 2. Выключаем
    qtbot.mouseClick(app.toggle_btn, Qt.LeftButton)
    qtbot.waitUntil(lambda: app.status_label.text() == "ОТКЛЮЧЕНО", timeout=3000)
    assert app.toggle_btn.isChecked() is False
    assert app.status_label.text() == "ОТКЛЮЧЕНО"

def test_server_dialog_add_remove(qtbot):
    dialog = ServerManagerDialog(["1.1.1.1:8080"])
    qtbot.addWidget(dialog)

    # Добавление сервера (проверяем заполнение структуры словаря)
    dialog.edit_address.setText("8.8.8.8:53")
    dialog.edit_user.setText("user1")
    dialog.edit_pass.setText("pass1")
    dialog.chk_tls.setChecked(True)
    dialog.edit_cert.setText("cert.pem")
    
    qtbot.mouseClick(dialog.btn_add, Qt.LeftButton)
    
    servers = dialog.get_servers()
    assert any(s["address"] == "8.8.8.8:53" and s["user"] == "user1" and s["tls"] is True for s in servers)

    # Удаление
    dialog.list_widget.setCurrentRow(0)
    qtbot.mouseClick(dialog.btn_remove, Qt.LeftButton)
    assert not any(s["address"] == "1.1.1.1:8080" for s in dialog.get_servers())

def test_process_dialog_add_remove(qtbot):
    dialog = ProcessManagerDialog(["Discord.exe"])
    qtbot.addWidget(dialog)

    # Добавление
    dialog.input_field.setText("steam.exe")
    qtbot.mouseClick(dialog.btn_add, Qt.LeftButton)
    assert "steam.exe" in dialog.get_processes()

def test_socks_mode_disables_split_tunneling_ui(app):
    """Проверяет, что выбор SOCKS-режима блокирует UI раздельного туннелирования."""
    app.radio_tun.click()
    assert app.chk_split.isEnabled() is True

    # Переключаем на SOCKS
    app.radio_socks.click()
    assert app.chk_split.isEnabled() is False
    assert app.btn_edit_apps.isEnabled() is False

def test_tun_mode_enables_split_tunneling_ui(app):
    """Проверяет, что выбор TUN-режима разрешает UI раздельного туннелирования."""
    app.radio_tun.click()
    assert app.chk_split.isEnabled() is True
    assert "Раздельное туннелирование" in app.chk_split.text()