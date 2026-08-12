import subprocess
import pytest
from src.network.route_manager import RouteManager

@pytest.fixture(autouse=True)
def reset_route_manager():
    rm = RouteManager()
    rm._is_modified = False
    rm.backup_gateway = None
    rm.backup_interface = None
    rm.backup_interface_index = None
    rm._last_server_ip = None
    yield rm
    rm._is_modified = False
    rm.backup_gateway = None
    rm.backup_interface = None
    rm.backup_interface_index = None
    rm._last_server_ip = None

def test_route_manager_backup_restore(monkeypatch):
    """Тестирует бэкап и откат шлюза без выполнения реальных системных команд."""
    rm = RouteManager()
    
    # 1. Имитируем вывод команды 'route print'
    def mock_check_output(cmd, *args, **kwargs):
        return (
            "Active Routes:\n"
            "Network Destination        Netmask          Gateway       Interface  Metric\n"
            "          0.0.0.0          0.0.0.0      192.168.1.1    192.168.1.100     25"
        )
        
    monkeypatch.setattr(subprocess, "check_output", mock_check_output)
    
    # 2. Имитируем успешный запуск утилиты route.exe
    commands_run = []
    def mock_run(cmd, *args, **kwargs):
        commands_run.append(cmd)
        class MockCompletedProcess:
            returncode = 0
            stdout = ""
        return MockCompletedProcess()
        
    monkeypatch.setattr(subprocess, "run", mock_run)
    
    # Проверяем получение шлюза
    gw, iface = rm.get_default_gateway()
    assert gw == "192.168.1.1"
    assert iface == "192.168.1.100"
    
    # Проверяем сохранение маршрутов
    assert rm.backup_routes() is True
    assert rm.backup_gateway == "192.168.1.1"
    
    # Проверяем восстановление маршрутов
    rm.restore_routes()
    assert rm.backup_gateway is None

def test_route_manager_idempotent_restore():
    """Повторный вызов отката маршрутов не должен выполнять никаких действий."""
    rm = RouteManager()
    rm.restore_routes()
    rm.restore_routes()
    assert rm.backup_gateway is None

def test_route_manager_setup_tun_routes(monkeypatch):
    """Проверяет корректность создания обходного пути для сервера в RouteManager (с изоляцией)."""
    rm = RouteManager()
    rm.backup_gateway = "192.168.1.1"
    rm.backup_interface = "1"
    
    # Имитируем 'route print'
    def mock_check_output(cmd, *args, **kwargs):
        return (
            "Active Routes:\n"
            "          0.0.0.0          0.0.0.0      192.168.1.1    10.0.0.100     25"
        )
        
    monkeypatch.setattr(subprocess, "check_output", mock_check_output)

    commands_run = []
    def mock_run(cmd, *args, **kwargs):
        commands_run.append(cmd)
        class MockCompletedProcess:
            returncode = 0
            stdout = ""
        return MockCompletedProcess()

    monkeypatch.setattr(subprocess, "run", mock_run)

    # Симулируем запуск маршрутизации TUN для сервера 93.186.225.208
    res = rm.setup_tun_routes(tun_gateway="10.0.0.1", server_ip="93.186.225.208")
    
    assert res is True
    assert rm._is_modified is True
    assert rm._last_server_ip == "93.186.225.208"
    
    # Проверяем, что команды обхода сформированы правильно
    assert any("route add 93.186.225.208 mask 255.255.255.255 192.168.1.1" in c for c in commands_run)
    
    # Проверяем откат
    commands_run.clear()
    rm.restore_routes()
    
    assert rm._is_modified is False
    assert any("route delete 93.186.225.208" in c for c in commands_run)