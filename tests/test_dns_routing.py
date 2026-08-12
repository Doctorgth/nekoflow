import json
import pytest
from src.network.tun_engine import TunEngine

def test_dns_routing_split_tunneling_whitelist_and_non_whitelist(tmp_path):
    """
    Проверяет, что при раздельном туннелировании:
    Все DNS-запросы резолвятся через безопасный dns-remote в туннеле,
    чтобы Windows DNS Client (svchost.exe) не блокировал DNS-запросы Edge/Chrome.
    """
    config_file = tmp_path / "singbox_dns_split.json"
    engine = TunEngine()
    engine.set_target_server({"address": "89.125.28.53:1050"})
    
    whitelist = ["chrome.exe", "Discord.exe"]
    engine.configure_split_tunneling(enabled=True, whitelist=whitelist)
    
    engine._generate_singbox_config(str(config_file))
    
    with open(config_file, "r", encoding="utf-8") as f:
        config = json.load(f)
        
    dns_config = config.get("dns", {})
    dns_servers = {s["tag"]: s for s in dns_config.get("servers", [])}
    
    assert "dns-direct" in dns_servers, "Отсутствует сервер dns-direct в конфигурации sing-box"
    assert dns_servers["dns-direct"]["detour"] == "direct", "Запросы dns-direct должны отправляться напрямую"
    assert dns_config.get("final") == "dns-direct", "Все DNS-запросы должны гарантированно обрабатываться через dns-direct"


def test_dns_routing_full_tunneling(tmp_path):
    """
    Проверяет, что при отключенном раздельном туннелировании (полный туннель):
    DNS резолвится локально напрямую (dns-direct), чтобы не туннелировать DNS-запросы.
    """
    config_file = tmp_path / "singbox_dns_full.json"
    engine = TunEngine()
    engine.set_target_server({"address": "89.125.28.53:1050"})
    
    engine.configure_split_tunneling(enabled=False, whitelist=["chrome.exe"])
    engine._generate_singbox_config(str(config_file))
    
    with open(config_file, "r", encoding="utf-8") as f:
        config = json.load(f)
        
    dns_config = config.get("dns", {})
    
    assert dns_config.get("final") == "dns-direct", "Final DNS должен быть dns-direct"
    assert len(dns_config.get("rules", [])) == 0, "В полном туннеле не должно быть выборочных DNS правил для процессов"