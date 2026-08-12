import asyncio
import threading
from typing import Dict, Any
from src.network.base_engine import BaseNetworkEngine

# Импортируем оригинального SOCKS5Server из папки client
try:
    from client.socks_server import SOCKS5Server
except ImportError:
    SOCKS5Server = None

class SocksEngine(BaseNetworkEngine):
    """
    Движок локального SOCKS-прокси, оборачивающий трафик в APTCP-туннель.
    Запускает SOCKS5Server из клиентской части APTCP на порту 3080.
    """

    def __init__(self):
        super().__init__()
        self.local_port = 3080
        self.server_config: Dict[str, Any] = {}
        self._loop: asyncio.AbstractEventLoop = None
        self._thread: threading.Thread = None
        self._socks_server = None

    def set_target_server(self, config: Dict[str, Any]) -> None:
        """Передает конфигурацию удаленного APTCP-сервера из UI."""
        self.server_config = config

    def start(self) -> bool:
        if not self.server_config.get("address"):
            print("[SOCKS] Ошибка: Не выбран целевой сервер!")
            return False

        if self.is_running:
            return True

        self._thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self._thread.start()
        self.is_running = True
        print(f"[SOCKS] Локальный SOCKS сервер запущен на порту {self.local_port}.")
        return True

    def _run_async_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        
        aptcp_host = self.server_config.get("address", "127.0.0.1")
        aptcp_port = int(self.server_config.get("port", 1080))

        # Конфигурируем SOCKS5Server для перенаправления в APTCP
        config = {
            "socks_host": "127.0.0.1",
            "socks_port": self.local_port,
            "auth_enabled": False,
            "aptcp_server_host": aptcp_host,
            "aptcp_server_port": aptcp_port,
            "aptcp_auth_enabled": bool(self.server_config.get("user")),
            "aptcp_username": self.server_config.get("user", ""),
            "aptcp_password": self.server_config.get("pass", ""),
            "aptcp_tls_enabled": self.server_config.get("tls", False),
            "aptcp_tls_ca_cert": self.server_config.get("cert"),
            "timeout": int(self.server_config.get("timeout", 30))
        }

        if SOCKS5Server:
            self._socks_server = SOCKS5Server(config)
            try:
                self._loop.run_until_complete(self._socks_server.start())
                self._loop.run_forever()
            except Exception as e:
                print(f"[SOCKS] Исключение в цикле asyncio: {e}")
            finally:
                try:
                    pending = [t for t in asyncio.all_tasks(self._loop) if not t.done()]
                    for task in pending:
                        task.cancel()
                    if pending and not self._loop.is_closed():
                        self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                except Exception:
                    pass
                finally:
                    if not self._loop.is_closed():
                        self._loop.close()
        else:
            print("[SOCKS] Предупреждение: SOCKS5Server не импортирован. Запущен холостой цикл.")
            try:
                self._loop.run_forever()
            except Exception:
                pass
            finally:
                self._loop.close()

    def stop(self) -> None:
        if not self.is_running:
            return

        if self._loop and self._socks_server and self._loop.is_running():
            async def _async_shutdown():
                if self._socks_server:
                    await self._socks_server.close()
                self._loop.stop()

            future = asyncio.run_coroutine_threadsafe(_async_shutdown(), self._loop)
            try:
                future.result(timeout=3.0)
            except Exception as e:
                print(f"[SOCKS] Ошибка остановки SOCKS сервера: {e}")

        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)

        if self._thread:
            self._thread.join(timeout=3.0)

        self._socks_server = None
        self._loop = None
        self._thread = None
        self.is_running = False
        print("[SOCKS] Движок SOCKS остановлен.")