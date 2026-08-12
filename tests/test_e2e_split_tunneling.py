import json
import pytest
from src.network.tun_engine import TunEngine

def test_e2e_split_tunneling_edge_browser_flow(tmp_path):
    """
    Сквозной e2e тест для Edge при Split Tunneling.

    Проверяем принципиально важное поведение:
    1. Обычный DNS (53) не зависит от whitelist.
    2. msedge.exe получает socks-out для своего обычного трафика.
    3. Secure DNS/DoH Edge не должен быть заблокирован искусственным
       правилом UDP/443.
    4. Остальные процессы по умолчанию идут в direct.
    """
    config_file = tmp_path / "singbox_e2e_edge.json"
    engine = TunEngine()
    engine.set_target_server({"address": "89.125.28.53:1050"})
    
    whitelist = ["msedge.exe", "chrome.exe"]
    engine.configure_split_tunneling(enabled=True, whitelist=whitelist)
    engine._generate_singbox_config(str(config_file))
    
    with open(config_file, "r", encoding="utf-8") as f:
        config = json.load(f)

    # 1. DNS должен оставаться глобальным и независимым от whitelist.
    dns_cfg = config.get("dns", {})
    assert dns_cfg.get("final") == "dns-direct", \
        "DNS должен использовать dns-direct напрямую без туннелирования"

    route_rules = config.get("route", {}).get("rules", [])

    # 2. Обычный DNS должен быть отправлен в dns-out.
    dns_port_rule = next(
        (r for r in route_rules
         if (r.get("port") == 53 or (isinstance(r.get("port"), list) and 53 in r.get("port")))
         and r.get("outbound") == "dns-out"),
        None
    )
    assert dns_port_rule is not None, \
        "DNS UDP/TCP 53 должен направляться в dns-out"

    dns_protocol_rule = next(
        (r for r in route_rules
         if r.get("protocol") == "dns" and r.get("outbound") == "dns-out"),
        None
    )
    assert dns_protocol_rule is not None, \
        "DNS protocol должен направляться в dns-out"

    # 3. Правило whitelist для Edge.
    
    edge_rule = None
    for r in route_rules:
        if r.get("outbound") == "socks-out" and "process_name" in r:
            edge_rule = r
            break
            
    assert edge_rule is not None, "Правило для процессов из белого списка не найдено"
    procs = [p.lower() for p in edge_rule.get("process_name", [])]
    assert "msedge.exe" in procs, "msedge.exe должен направляться в socks-out"

    # 4. Дефолтный маршрут для остальных процессов должен быть direct.
    assert config.get("route", {}).get("final") == "direct"

    # 5. Не должно существовать глобального правила, блокирующего UDP/443.
    # Edge может использовать Secure DNS / QUIC, и этот трафик должен
    # определяться обычным process_name == msedge.exe.
    blocked_udp_443 = [
        r for r in route_rules
        if r.get("network") == "udp"
        and r.get("port") == 443
        and r.get("outbound") == "block"
    ]
    assert not blocked_udp_443, \
        "Глобальная блокировка UDP/443 ломает Secure DNS/QUIC whitelist-приложений"