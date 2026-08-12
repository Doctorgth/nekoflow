import pytest
from src.network.socks_engine import SocksEngine
from src.network.tun_engine import TunEngine

def test_base_engine_split_tunneling():
    engine = SocksEngine()
    engine.configure_split_tunneling(True, ["Discord.exe", "python.exe"])
    
    assert engine.split_tunneling is True
    assert "discord.exe" in engine.whitelist
    assert "python.exe" in engine.whitelist

def test_engine_admin_check_failure(monkeypatch):
    # Эмулируем отсутствие прав админа
    monkeypatch.setattr("src.network.tun_engine.is_admin", lambda: False)

    tun = TunEngine()
    assert tun.start() is False

def test_socks_engine_start_stop(monkeypatch):
    socks = SocksEngine()
    
    socks.set_target_server({
        "address": "127.0.0.1:9090",
        "user": "admin",
        "pass": "secret"
    })
    
    class MockSocksServer:
        def __init__(self, config):
            self.config = config
        async def start(self):
            pass
        async def close(self):
            pass

    monkeypatch.setattr("src.network.socks_engine.SOCKS5Server", MockSocksServer)

    assert socks.start() is True
    assert socks.is_running is True
    socks.stop()
    assert socks.is_running is False