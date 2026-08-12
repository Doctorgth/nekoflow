import json
import pytest
from src.network.tun_engine import TunEngine

def test_singbox_rules_split_tunneling_traffic(tmp_path):
    """
    Проверяет, что при Split Tunneling = True:
    - Процессы из белого списка идут в outbound: socks-out.
    - Системные процессы (NekoFlow.exe, sing-box.exe) и остальные процессы идут в outbound: direct.
    """
    config_file = tmp_path / "singbox_split_traffic.json"
    engine = TunEngine()
    engine.set_target_server({"address": "77.105.128.154:1050"})
    
    whitelist = ["archeage.exe", "chrome.exe"]
    engine.configure_split_tunneling(enabled=True, whitelist=whitelist)
    engine._generate_singbox_config(str(config_file))
    
    with open(config_file, "r", encoding="utf-8") as f:
        config = json.load(f)
        
    route_cfg = config.get("route", {})
    rules = route_cfg.get("rules", [])
    
    # 1. По умолчанию всё не указанное должно идти напрямую
    assert route_cfg.get("final") == "direct"
    
    # 2. Находим правило туннелирования процессов
    socks_rule = None
    system_rule = None
    for r in rules:
        if r.get("outbound") == "socks-out":
            socks_rule = r
        elif r.get("outbound") == "direct" and "process_name" in r:
            system_rule = r
            
    assert socks_rule is not None, "Правило маршрутизации трафика для белого списка не найдено"
    procs = socks_rule.get("process_name", [])
    
    for app in whitelist:
        assert any(app.lower() == p.lower() for p in procs), f"Приложение {app} отсутствует в правилах туннелирования"

    # 3. Системные процессы обязательно изолированы в direct
    assert system_rule is not None, "Правило изоляции системных процессов от туннеля не найдено"
    sys_procs = system_rule.get("process_name", [])
    assert any("nekoflow.exe" in p.lower() for p in sys_procs)
    assert any("sing-box.exe" in p.lower() for p in sys_procs)


def test_singbox_rules_full_tunneling_traffic(tmp_path):
    """
    Проверяет, что при Split Tunneling = False (Полный туннель):
    - Весь трафик по умолчанию идет в outbound: socks-out.
    - Локальные сети и служебные процессы идут в direct.
    """
    config_file = tmp_path / "singbox_full_traffic.json"
    engine = TunEngine()
    engine.set_target_server({"address": "77.105.128.154:1050"})
    
    engine.configure_split_tunneling(enabled=False, whitelist=["chrome.exe"])
    engine._generate_singbox_config(str(config_file))
    
    with open(config_file, "r", encoding="utf-8") as f:
        config = json.load(f)
        
    route_cfg = config.get("route", {})
    
    # По умолчанию весь трафик направляется в туннель
    assert route_cfg.get("final") == "socks-out"
    
    rules = route_cfg.get("rules", [])
    # Присутствует исключение для частных подсетей (10.0.0.0/8, 192.168.0.0/16)
    local_ip_rule = None
    for r in rules:
        if r.get("outbound") == "direct" and "ip_cidr" in r:
            cidrs = r.get("ip_cidr", [])
            if "10.0.0.0/8" in cidrs or "192.168.0.0/16" in cidrs:
                local_ip_rule = r
                break
                
    assert local_ip_rule is not None, "В полном туннеле должны присутствовать обходные пути для локальной сети"