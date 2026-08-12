import os
import asyncio
import pytest
from unittest.mock import AsyncMock, patch
from client.socks_server import SOCKS5Server, _setup_whitelist_logger
from common.socks5 import REP_SUCCESS

def test_whitelist_logger_disabled(tmp_path):
    """Проверяет, что детальный логгер белого списка успешно отключен и не создает файлы."""
    log_file = tmp_path / "whitelist_debug.log"
    wl_logger = _setup_whitelist_logger(str(log_file))

    wl_logger.info("ТЕСТОВОЕ СООБЩЕНИЕ ЛОГГЕРА БЕЛОГО СПИСКА")

    assert not os.path.exists(log_file)

def test_socks_server_runs_without_whitelist_log_errors(tmp_path):
    """Проверяет, что при обработке соединения SOCKS5Server работает без ошибок логгирования."""
    log_file = tmp_path / "whitelist_debug_test.log"
    _setup_whitelist_logger(str(log_file))

    async def _run():
        config = {
            "socks_host": "127.0.0.1",
            "socks_port": 0,
            "aptcp_server_host": "127.0.0.1",
            "aptcp_server_port": 1080
        }
        server = SOCKS5Server(config)

        mock_stream = AsyncMock()
        mock_stream.read.return_value = b""

        async def mock_read_resp(stream):
            return REP_SUCCESS, 1, "0.0.0.0", 0

        with patch("client.socks_server.APTCPTunnelClient.connect_and_authenticate", return_value=mock_stream), \
             patch("client.socks_server.send_tunnel_cmd_request", return_value=True), \
             patch("client.socks_server.read_tunnel_cmd_response", side_effect=mock_read_resp), \
             patch.object(server, "_relay_tcp_logged", new_callable=AsyncMock):

            mock_reader = AsyncMock()
            mock_reader.readexactly.side_effect = [
                bytes([5, 1]),       # ver, nmethods
                bytes([0]),          # method
                bytes([5, 1]),       # ver, cmd (CONNECT)
                bytes([0]),          # rsv
                bytes([1]),          # atyp IPV4
                bytes([127, 0, 0, 1]),
                bytes([0, 80])       # port 80
            ]
            mock_reader.read.return_value = b""

            mock_writer = AsyncMock()
            mock_writer.get_extra_info.return_value = ("127.0.0.1", 54321)

            await server.handle_client(mock_reader, mock_writer)

    asyncio.run(_run())

    assert not os.path.exists(log_file)