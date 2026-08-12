import asyncio
import socket
import logging
from typing import Optional

from common.socks5 import (
    SOCKS_VERSION, METHOD_NO_AUTH, CMD_CONNECT, REP_SUCCESS,
    REP_GENERAL_FAILURE, REP_CMD_NOT_SUPPORTED,
    read_socks_address, pack_socks_address
)

logger = logging.getLogger("DirectSOCKS5")


class DirectSOCKS5Server:
    """
    Прямой локальный SOCKS5 ретранслятор без PTCP туннелирования.
    Принимает сокет от sing-box и от своего имени открывает прямое TCP-соединение к хосту.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 3080):
        self.socks_host = host
        self.socks_port = port
        self._server = None

    async def start(self):
        self._server = await asyncio.start_server(
            self.handle_client, self.socks_host, self.socks_port, reuse_address=True
        )
        print(f"[DirectSOCKS] Прямой ретранслятор запущен на {self.socks_host}:{self.socks_port}")

    async def serve_forever(self):
        if self._server:
            await self._server.serve_forever()

    async def close(self):
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            # 1. Рукопожатие SOCKS5
            header = await reader.readexactly(2)
            ver, nmethods = header[0], header[1]
            if ver != SOCKS_VERSION:
                writer.close()
                await writer.wait_closed()
                return

            _ = await reader.readexactly(nmethods)
            writer.write(bytes([SOCKS_VERSION, METHOD_NO_AUTH]))
            await writer.drain()

            # 2. Чтение команды
            req_header = await reader.readexactly(2)
            _, cmd = req_header[0], req_header[1]
            _ = await reader.readexactly(1)  # RSV
            atyp, target_host, target_port, _ = await read_socks_address(reader.readexactly)

            if cmd != CMD_CONNECT:
                rep_bytes = bytes([SOCKS_VERSION, REP_CMD_NOT_SUPPORTED, 0x00]) + pack_socks_address("0.0.0.0", 0)
                writer.write(rep_bytes)
                await writer.drain()
                writer.close()
                await writer.wait_closed()
                return

            # 3. Прямое подключение к целевому хосту без туннеля
            try:
                remote_reader, remote_writer = await asyncio.wait_for(
                    asyncio.open_connection(target_host, target_port),
                    timeout=10.0
                )
            except Exception as e:
                logger.error(f"[DirectSOCKS] Не удалось подключиться к {target_host}:{target_port}: {e}")
                rep_bytes = bytes([SOCKS_VERSION, REP_GENERAL_FAILURE, 0x00]) + pack_socks_address("0.0.0.0", 0)
                writer.write(rep_bytes)
                await writer.drain()
                writer.close()
                await writer.wait_closed()
                return

            # 4. Успешный ответ клиенту
            rep_bytes = bytes([SOCKS_VERSION, REP_SUCCESS, 0x00]) + pack_socks_address("0.0.0.0", 0)
            writer.write(rep_bytes)
            await writer.drain()

            # 5. Двунаправленная пересылка сырых данных
            async def relay(src_reader: asyncio.StreamReader, dst_writer: asyncio.StreamWriter):
                try:
                    while True:
                        data = await src_reader.read(65536)
                        if not data:
                            break
                        dst_writer.write(data)
                        await dst_writer.drain()
                except Exception:
                    pass

            t1 = asyncio.create_task(relay(reader, remote_writer))
            t2 = asyncio.create_task(relay(remote_reader, writer))

            try:
                await asyncio.wait([t1, t2], return_when=asyncio.FIRST_COMPLETED)
            finally:
                for t in (t1, t2):
                    t.cancel()
                await asyncio.gather(t1, t2, return_exceptions=True)
                try:
                    remote_writer.close()
                    await remote_writer.wait_closed()
                except Exception:
                    pass

        except Exception:
            pass
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass