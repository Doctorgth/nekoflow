import asyncio
import pytest
from unittest.mock import AsyncMock, patch
from client.socks_server import SOCKS5Server
from common.socks5 import SOCKS_VERSION, REP_SUCCESS

def test_poc_edge_local_domain_resolution_fix():
    """
    ПРУФ-ТЕСТ: Проверяет, что SOCKS5Server автоматически резолвит доменные имена (ya.ru)
    в IPv4-адрес на локальном ПК пользователя перед отправкой команды на удаленный APTCP-сервер.
    """
    async def _run():
        config = {
            "socks_host": "127.0.0.1",
            "socks_port": 0,
            "aptcp_server_host": "127.0.0.1",
            "aptcp_server_port": 1080
        }
        server = SOCKS5Server(config)

        mock_stream = AsyncMock()
        
        # Перехваченная отправка команды в туннель
        sent_hosts = []
        async def mock_send_cmd(stream, cmd, host, port):
            sent_hosts.append(host)
            return True

        async def mock_read_resp(stream):
            return REP_SUCCESS, 1, "0.0.0.0", 0

        with patch("client.socks_server.APTCPTunnelClient.connect_and_authenticate", return_value=mock_stream), \
             patch("client.socks_server.send_tunnel_cmd_request", side_effect=mock_send_cmd), \
             patch("client.socks_server.read_tunnel_cmd_response", side_effect=mock_read_resp), \
             patch.object(server, "_relay_tcp", new_callable=AsyncMock):

            mock_reader = AsyncMock()
            # Отправляем SOCKS5 CONNECT запрос с ДОМЕННЫМ ИМЕНЕМ "ya.ru"
            domain_bytes = b"ya.ru"
            mock_reader.readexactly.side_effect = [
                bytes([5, 1]),       # ver, nmethods
                bytes([0]),          # method
                bytes([5, 1]),       # ver, cmd
                bytes([0]),          # rsv
                bytes([3]),          # atyp DOMAIN
                bytes([len(domain_bytes)]),
                domain_bytes,        # "ya.ru"
                bytes([0, 80])       # port 80
            ]
            mock_reader.read.return_value = b""

            mock_writer = AsyncMock()
            mock_writer.drain = AsyncMock()
            mock_writer.wait_closed = AsyncMock()

            await server.handle_client(mock_reader, mock_writer)

            assert len(sent_hosts) == 1
            # Убеждаемся, что в туннель ушел IPv4-адрес, а не сырой домен "ya.ru"
            assert sent_hosts[0] != "ya.ru", "ОШИБКА: Домен 'ya.ru' был отправлен на сервер в сыром виде вместо резолва в IP!"

    asyncio.run(_run())