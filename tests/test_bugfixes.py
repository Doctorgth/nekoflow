import asyncio
import socket
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch

from client.socks_server import SOCKS5Server
from common.socks5 import (
    SOCKS_VERSION, CMD_CONNECT, REP_SUCCESS, parse_udp_packet
)
from src.network.tun_engine import TunEngine


def test_udp_zero_byte_first_byte_is_packed():
    """
    Проверяет фикс бага UDP:
    Когда сервер отдает UDP-фрейм с первым байтом 0x00 (например, DNS-ответ или пакет игры),
    SOCKS5Server ОБЯЗАН обернуть его в SOCKS5 UDP-заголовок, а не отправлять сырым.
    """
    async def _run():
        config = {
            "socks_host": "127.0.0.1",
            "socks_port": 0,
            "aptcp_server_host": "127.0.0.1",
            "aptcp_server_port": 1080
        }
        server = SOCKS5Server(config)

        loop = asyncio.get_running_loop()

        client_udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client_udp.bind(("127.0.0.1", 0))
        client_udp.setblocking(False)

        zero_first_byte_payload = b"\x00\x12\x34\x56\x78\x90\xab\xcd"
        
        mock_ptcp_stream = AsyncMock()

        server_udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        server_udp.bind(("127.0.0.1", 0))
        server_udp.setblocking(False)

        reader = AsyncMock()
        reader.read.return_value = b""
        writer = AsyncMock()

        with patch("client.socks_server.read_udp_frame", side_effect=[zero_first_byte_payload, asyncio.CancelledError()]):
            relay_task = asyncio.create_task(
                server._relay_udp(reader, writer, server_udp, mock_ptcp_stream)
            )

            server_udp_addr = server_udp.getsockname()
            dummy_socks_udp_req = b"\x00\x00\x00\x01\x08\x08\x08\x08\x00\x35hello"
            client_udp.sendto(dummy_socks_udp_req, server_udp_addr)

            received_data, _ = await asyncio.wait_for(
                loop.sock_recvfrom(client_udp, 65536),
                timeout=2.0
            )

            relay_task.cancel()
            try:
                await relay_task
            except (asyncio.CancelledError, Exception):
                pass

        client_udp.close()
        server_udp.close()

        rsv, frag, atyp, dst_host, dst_port, payload = parse_udp_packet(received_data)
        assert payload == zero_first_byte_payload, "Payload не совпадает с отправленным кадром с 0x00 байтом"

    asyncio.run(_run())





def test_singbox_config_stack_and_dns_fixes(tmp_path):
    """
    Проверяет конфиг sing-box:
    1. stack == 'mixed' (для предотвращения крашей Windows системного стека).
    2. dns-remote использует 'tcp://8.8.8.8' (гарантия доставки DNS без потерь).
    """
    config_file = tmp_path / "test_singbox_fixes.json"
    engine = TunEngine()
    engine.set_target_server({"address": "89.125.28.53:1050"})
    
    engine._generate_singbox_config(str(config_file))
    
    with open(config_file, "r", encoding="utf-8") as f:
        config = json.load(f)
        
    inbound = config.get("inbounds", [])[0]
    assert inbound.get("stack") == "mixed", "TUN inbound должен использовать stack 'mixed'"
    
    dns_servers = {s["tag"]: s for s in config.get("dns", {}).get("servers", [])}
    assert dns_servers["dns-remote"]["address"] == "tcp://8.8.8.8", "dns-remote должен использовать TCP транспорт"