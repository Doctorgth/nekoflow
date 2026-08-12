import sys
import time
import threading
import subprocess
import os
import json
import asyncio
import socket
import ipaddress
import psutil
from typing import Tuple, Optional
from src.network.base_engine import BaseNetworkEngine
from src.network.route_manager import RouteManager
from src.utils.admin import is_admin

# Импортируем SOCKS5-серверы
try:
    from client.socks_server import SOCKS5Server
except ImportError:
    SOCKS5Server = None

try:
    from client.direct_socks_server import DirectSOCKS5Server
except ImportError:
    DirectSOCKS5Server = None

class TunEngine(BaseNetworkEngine):
    """Движок перехвата трафика через виртуальный TUN интерфейс на базе sing-box."""

    def __init__(self):
        super().__init__()
        self.route_manager = RouteManager()
        self._stop_event = threading.Event()
        self._tun2socks_proc: Optional[subprocess.Popen] = None
        self.tun_ip = "10.0.0.2"
        self.tun_gw = "10.0.0.1"
        self.tun_name = "NekoFlow"
        self.local_socks_port = 3080
        self.server_config: dict = {}
        self.use_direct_relay = False  # Переключено на боевой APTCP-сервер

        # Ресурсы встроенного локального SOCKS5 транслятора
        self._socks_thread: Optional[threading.Thread] = None
        self._socks_loop: Optional[asyncio.AbstractEventLoop] = None
        self._socks_server = None

    def set_target_server(self, config: dict) -> None:
        self.server_config = config

    def _kill_zombie_singbox(self) -> None:
        """Принудительно завершает старые процессы sing-box."""
        try:
            subprocess.run("taskkill /F /IM sing-box.exe", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(0.3)
        except Exception:
            pass

    def _destroy_interface(self) -> None:
        """Удаление виртуального адаптера через PowerShell."""
        try:
            # Сначала пробуем выключить, чтобы Windows быстрее освободила ресурсы
            subprocess.run(f'powershell -Command "Disable-NetAdapter -Name \'{self.tun_name}\' -Confirm:$false"', 
                           shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(0.2)
            cmd = f'powershell -Command "Get-NetAdapter | Where-Object {{ $_.Name -like \'{self.tun_name}\' -or $_.InterfaceDescription -like \'*Wintun*\' }} | Remove-NetAdapter -Confirm:$false"'
            subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    async def _verify_tunnel_connection(self) -> Tuple[bool, str]:
        """Тестовое подключение к удаленному серверу перед основным запуском."""
        try:
            from client.aptcp_client import APTCPTunnelClient
            from common.tunnel import send_tunnel_cmd_request, read_tunnel_cmd_response
            from common.socks5 import CMD_CONNECT, REP_SUCCESS
        except ImportError as e:
            return False, f"Ошибка импорта библиотек: {e}"

        aptcp_host = self.server_config.get("address", "127.0.0.1").split(":")[0]
        aptcp_port = int(self.server_config.get("port", 1080))

        tunnel_client = APTCPTunnelClient(
            aptcp_host, aptcp_port,
            tls_enabled=self.server_config.get("tls", False),
            tls_ca_cert=self.server_config.get("cert")
        )

        try:
            ptcp_stream = await tunnel_client.connect_and_authenticate(
                auth_enabled=bool(self.server_config.get("user")),
                username=self.server_config.get("user", ""),
                password=self.server_config.get("pass", "")
            )
            await send_tunnel_cmd_request(ptcp_stream, CMD_CONNECT, "example.com", 80)
            rep, _, _, _ = await read_tunnel_cmd_response(ptcp_stream)
            await ptcp_stream.close()
            return True, ""
        except Exception as e:
            return False, str(e)

    def start(self) -> bool:
        if not is_admin():
            print("[TUN] Ошибка: Требуются права Администратора!")
            return False

        if not self.server_config or not self.server_config.get("address"):
            print("[TUN] Ошибка: Сервер не выбран!")
            return False

        # 1. Тщательная зачистка перед стартом (как в NekoBox)
        print("[TUN] Подготовка системы...")
        self._kill_zombie_singbox()
        self._destroy_interface()
        time.sleep(1.0) 

        # 2. Проверка связи с сервером
        print("[TUN] Проверка авторизации на сервере...")
        try:
            success, err_msg = asyncio.run(self._verify_tunnel_connection())
            if not success:
                raise RuntimeError(f"Сервер недоступен или ошибка логина: {err_msg}")
        except Exception as e:
            print(f"[TUN] Тест не пройден: {e}")
            raise

        # 3. Резервное копирование маршрутов
        if not self.route_manager.backup_routes():
            return False

        # Валидация IP-адреса сервера для предотвращения петли маршрутизации
        raw_server_ip = self.server_config.get("address", "").split(":")[0]
        try:
            server_ip = socket.gethostbyname(raw_server_ip)
            ipaddress.ip_address(server_ip) # Проверяем корректность IPv4
        except Exception as e:
            raise RuntimeError(f"Невозможно определить IP-адрес сервера '{raw_server_ip}': {e}")

        # 4. Запуск локального SOCKS-транслятора
        if SOCKS5Server:
            self._socks_thread = threading.Thread(target=self._run_socks_loop, daemon=True)
            self._socks_thread.start()
            time.sleep(0.5)

        # 5. Генерация конфига и запуск sing-box
        config_path = os.path.abspath("connecter_singbox.json")
        self._generate_singbox_config(config_path)

        singbox_bin = os.path.abspath("bin/sing-box.exe")
        bin_dir = os.path.dirname(singbox_bin)

        if not os.path.exists(singbox_bin):
            raise FileNotFoundError(f"Файл {singbox_bin} не найден!")

        print("[TUN] Запуск ядра sing-box...")
        cmd = [singbox_bin, "run", "-c", config_path]
        
        # Пишем логи в файл. Это спасет от Deadlock-а пайпов и позволит прочитать ошибку при краше.
        self._sb_log_file = open("singbox.log", "w", encoding="utf-8")
        # Указываем cwd=bin_dir, чтобы sing-box нашел wintun.dll в своей папке
        self._tun2socks_proc = subprocess.Popen(
            cmd, stdout=self._sb_log_file, stderr=subprocess.STDOUT,
            cwd=bin_dir,
            creationflags=subprocess.CREATE_NO_WINDOW
        )

        # 6. Верификация адаптера (увеличили таймаут)
        if not self._verify_tun_adapter_active(timeout=10.0):
            self.stop()
            raise RuntimeError("Виртуальный адаптер не создан. Проверьте наличие bin/wintun.dll и права админа.")

        # 7. Установка маршрутов с гарантированно корректным IP
        if not self.route_manager.setup_tun_routes(self.tun_gw, server_ip):
            self.stop()
            return False

        self.is_running = True
        return True

    def _generate_singbox_config(self, path: str):
        raw_addr = self.server_config.get("address", "").split(":")[0]
        server_ip = None
        # Строгая валидация IP-адреса, чтобы sing-box не крашнулся от мусора в конфиге
        try:
            resolved_ip = socket.gethostbyname(raw_addr)
            ipaddress.ip_address(resolved_ip)
            server_ip = resolved_ip
        except Exception:
            pass

        outbounds = [
            {"type": "socks", "tag": "socks-out", "server": "127.0.0.1", "server_port": self.local_socks_port},
            {"type": "direct", "tag": "direct"},
            {"type": "dns", "tag": "dns-out"},
            {"type": "block", "tag": "block"}
        ]

        process_names = set()
        if self.whitelist:
            for p in self.whitelist:
                process_names.add(p)
                process_names.add(p.lower())
                process_names.add(p.capitalize())
                process_names.add(p.upper())

        # Надежное получение имени процесса, даже если лаунчер переименовали
        try:
            current_proc = psutil.Process(os.getpid()).name()
        except Exception:
            current_proc = os.path.basename(sys.executable)

        system_procs = list(set([
            "NekoFlow.exe", "python.exe", "pythonw.exe", "sing-box.exe", 
            "NekoLauncher.exe", current_proc, current_proc.lower(), current_proc.capitalize()
        ]))

        # НАИВЫСШИЙ ПРИОРИТЕТ: Направление всех DNS-запросов в встроенный DNS-движок sing-box (dns-out)
        # Использование FakeIP гарантирует мгновенные (< 1 мс) ответы приложениям без задержек сети.
        doh_domains = ["dns.google", "cloudflare-dns.com", "nextdns.io", "dns.quad9.net", "common.dot.dns.yandex.net"]
        doh_ips = ["1.1.1.1/32", "1.0.0.1/32", "8.8.8.8/32", "8.8.4.4/32", "9.9.9.9/32"]

        rules = [
            {"port": [53, 853, 5353], "outbound": "dns-out"},
            {"protocol": "dns", "outbound": "dns-out"},
            {"domain_suffix": doh_domains, "outbound": "direct"},
            {"ip_cidr": doh_ips, "outbound": "direct"},
            {"process_name": system_procs, "outbound": "direct"},
            {"ip_cidr": ["127.0.0.0/8", "::1/128"], "outbound": "direct"}
        ]

        if server_ip:
            rules.append({"ip_cidr": [f"{server_ip}/32"], "outbound": "direct"})

        if self.split_tunneling and self.whitelist:
            # Раздельное туннелирование: в туннель идут только указанные процессы
            rules.append({"process_name": list(process_names), "outbound": "socks-out"})
            default_out = "direct"
        else:
            # Полный туннель: исключаем локальные сети и пускаем остальное в туннель
            rules.append({"ip_cidr": ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"], "outbound": "direct"})
            default_out = "socks-out"

        config = {
            "log": {"level": "warn"},
            "dns": {
                "servers": [
                    {"tag": "dns-direct", "address": "1.1.1.1", "detour": "direct"},
                    {"tag": "dns-remote", "address": "tcp://8.8.8.8", "detour": "socks-out"}
                ],
                "rules": [],
                "final": "dns-direct",
                "strategy": "ipv4_only",
                "independent_cache": True
            },
            "inbounds": [{
                "type": "tun",
                "tag": "tun-in",
                "interface_name": self.tun_name,
                "inet4_address": ["10.0.0.2/24"],
                "auto_route": True,
                "strict_route": False,
                "stack": "mixed",
                "mtu": 1500,
                "sniff": False,
                "sniff_override_destination": False
            }],
            "outbounds": outbounds,
            "route": {
                "rules": rules,
                "final": default_out,
                "auto_detect_interface": True
            }
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)

    def _verify_tun_adapter_active(self, timeout: float) -> bool:
        import re
        start = time.time()
        while time.time() - start < timeout:
            # 1. Если процесс упал, вытаскиваем понятную ошибку из лога и кидаем ее пользователю в UI
            if self._tun2socks_proc and self._tun2socks_proc.poll() is not None:
                err_text = ""
                try:
                    if hasattr(self, "_sb_log_file") and self._sb_log_file:
                        self._sb_log_file.flush()
                    with open("singbox.log", "r", encoding="utf-8") as f:
                        err_text = f.read().strip()
                except Exception:
                    pass
                
                # Чистим цветные консольные символы ANSI
                clean_err = re.sub(r'\x1b\[[0-9;]*[mGKH]', '', err_text)
                last_lines = "\n".join([line for line in clean_err.splitlines() if line.strip()][-5:])
                if not last_lines:
                    last_lines = "Процесс sing-box аварийно завершился без сообщений в логе."
                
                raise RuntimeError(f"Ошибка ядра sing-box:\n{last_lines}")

            # 2. Сверхбыстрая проверка наличия адреса 10.0.0.2 через C-API psutil без тяжелых подпроцессов
            try:
                addrs = psutil.net_if_addrs()
                for iface_name, iface_addrs in addrs.items():
                    if self.tun_name.lower() in iface_name.lower():
                        for addr in iface_addrs:
                            if addr.address == "10.0.0.2":
                                return True
            except Exception:
                pass
                
            time.sleep(0.2)
            
        # Забираем подробности при таймауте адаптера
        err_details = ""
        try:
            with open("singbox.log", "r", encoding="utf-8") as f:
                raw_log = f.read().strip()
                clean_log = re.sub(r'\x1b\[[0-9;]*[mGKH]', '', raw_log)
                err_details = "\n" + "\n".join(clean_log.splitlines()[-4:])
        except Exception:
            pass

        raise RuntimeError(f"Виртуальный адаптер {self.tun_name} не ответил за {int(timeout)} сек.{err_details}")

    def stop(self) -> None:
        if not self.is_running and not self._tun2socks_proc:
            return
        
        self._stop_event.set()
        self.route_manager.restore_routes()

        if self._tun2socks_proc:
            self._tun2socks_proc.terminate()
            try: self._tun2socks_proc.wait(timeout=2)
            except: self._tun2socks_proc.kill()
            self._tun2socks_proc = None

        try:
            if hasattr(self, "_sb_log_file") and self._sb_log_file:
                self._sb_log_file.close()
        except: pass

        self._stop_socks_server()
        self._destroy_interface()
        
        for f in ["connecter_singbox.json", "connecter_windivert_singbox.json"]:
            if os.path.exists(f):
                try: os.remove(f)
                except: pass

        self.is_running = False

    def _run_socks_loop(self):
        self._socks_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._socks_loop)
        
        # Проверяем, включен ли режим прямого ретранслятора (для отладки)
        if self.use_direct_relay or self.server_config.get("direct_relay", False):
            print("[TUN SOCKS] ВНИМАНИЕ: Запущен ПРЯМОЙ SOCKS5 ретранслятор (без PTCP туннелирования)!")
            if DirectSOCKS5Server:
                self._socks_server = DirectSOCKS5Server("127.0.0.1", self.local_socks_port)
            else:
                raise ImportError("DirectSOCKS5Server модуль не найден.")
        else:
            config = {
                "socks_host": "127.0.0.1",
                "socks_port": self.local_socks_port,
                "auth_enabled": False,
                "aptcp_server_host": self.server_config.get("address").split(":")[0],
                "aptcp_server_port": int(self.server_config.get("port", 1080)),
                "aptcp_auth_enabled": bool(self.server_config.get("user")),
                "aptcp_username": self.server_config.get("user", ""),
                "aptcp_password": self.server_config.get("pass", ""),
                "aptcp_tls_enabled": self.server_config.get("tls", False),
                "aptcp_tls_ca_cert": self.server_config.get("cert"),
                "timeout": int(self.server_config.get("timeout", 30))
            }
            self._socks_server = SOCKS5Server(config)
        
        try:
            self._socks_loop.run_until_complete(self._socks_server.start())
            self._socks_loop.run_forever()
        except Exception as e:
            print(f"[TUN SOCKS] Ошибка в асинхронном цикле: {e}")
        finally:
            # Безопасное гашение незавершенных задач без вызова run_until_complete на остановленном loop
            try:
                pending = [t for t in asyncio.all_tasks(self._socks_loop) if not t.done()]
                for task in pending:
                    task.cancel()
                if pending and not self._socks_loop.is_closed():
                    self._socks_loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            except Exception:
                pass
            finally:
                if not self._socks_loop.is_closed():
                    self._socks_loop.close()

    def _stop_socks_server(self):
        if self._socks_loop and self._socks_server and self._socks_loop.is_running():
            async def _async_shutdown():
                if self._socks_server:
                    await self._socks_server.close()
                self._socks_loop.stop()

            future = asyncio.run_coroutine_threadsafe(_async_shutdown(), self._socks_loop)
            try:
                future.result(timeout=3.0)
            except Exception:
                pass

        if self._socks_loop and self._socks_loop.is_running():
            self._socks_loop.call_soon_threadsafe(self._socks_loop.stop)
            
        if self._socks_thread:
            self._socks_thread.join(timeout=3.0)
            
        self._socks_server = None
        self._socks_loop = None
        self._socks_thread = None