import subprocess
import re
import os
import json
from typing import Optional, Tuple

class RouteManager:
    """Модуль управления таблицей маршрутизации Windows и аварийного восстановления."""
    
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(RouteManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    @staticmethod
    def force_cleanup_leftovers():
        """Очищает маршруты и адаптеры, принадлежащие ИСКЛЮЧИТЕЛЬНО NekoFlow."""
        try:
            subprocess.run("route delete 0.0.0.0 mask 128.0.0.0", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run("route delete 128.0.0.0 mask 128.0.0.0", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

        try:
            # Удаляем виртуальные адаптеры строго по точному имени NekoFlow
            cmd = 'powershell -Command "Get-NetAdapter | Where-Object { $_.Name -eq \'NekoFlow\' } | Remove-NetAdapter -Confirm:$false"'
            subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

        # --- АВАРИЙНАЯ ОЧИСТКА СИСТЕМНОГО ПРОКСИ WINDOWS ---
        try:
            import winreg
            import ctypes
            internet_settings = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r'Software\Microsoft\Windows\CurrentVersion\Internet Settings',
                0, winreg.KEY_ALL_ACCESS
            )
            winreg.SetValueEx(internet_settings, "ProxyEnable", 0, winreg.REG_DWORD, 0)
            winreg.CloseKey(internet_settings)

            # Уведомляем систему о снятии прокси немедленно
            internet_set_option = ctypes.windll.wininet.InternetSetOptionW
            internet_set_option(0, 39, 0, 0)
            internet_set_option(0, 37, 0, 0)
            print("[RouteManager] Системный прокси Windows успешно сброшен (аварийная очистка).")
        except Exception:
            pass

    def __init__(self):
        if self._initialized:
            return
        self.backup_gateway: Optional[str] = None
        self.backup_interface: Optional[str] = None
        self.backup_interface_index: Optional[int] = None
        self._is_modified = False
        self._last_server_ip: Optional[str] = None
        self._initialized = True

    def get_default_gateway(self) -> Tuple[Optional[str], Optional[str]]:
        """Возвращает (Gateway IP, Interface Name/Index) по умолчанию с наименьшей метрикой (основной рабочий интернет)."""
        best_gateway = None
        best_interface = None
        lowest_metric = 999999

        try:
            output = subprocess.check_output("route print 0.0.0.0", shell=True, text=True)
            for line in output.splitlines():
                line = line.strip()
                if line.startswith("0.0.0.0"):
                    parts = re.split(r'\s+', line)
                    if len(parts) >= 5:
                        gateway = parts[2]
                        interface = parts[3]
                        try:
                            metric = int(parts[4])
                        except ValueError:
                            metric = 99999

                        if gateway in ("127.0.0.1", "10.0.0.1") or not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', gateway):
                            continue

                        if metric < lowest_metric:
                            lowest_metric = metric
                            best_gateway = gateway
                            best_interface = interface
            
            if best_gateway:
                print(f"[RouteManager] Автоопределение шлюза: GW={best_gateway}, IF={best_interface}, Metric={lowest_metric}")
                return best_gateway, best_interface
        except Exception as e:
            print(f"[RouteManager] Ошибка получения дефолтного шлюза: {e}")
        
        return None, None

    def backup_routes(self) -> bool:
        if self.backup_gateway:
            return True

        gw, iface = self.get_default_gateway()
        if gw:
            self.backup_gateway = gw
            self.backup_interface = iface
            print(f"[RouteManager] Бэкап шлюза успешн: GW={gw}, IF={iface}")
            
            try:
                cmd = f'powershell -Command "Get-NetIPAddress -IPAddress {iface} | Select-Object -ExpandProperty InterfaceIndex"'
                res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if res.returncode == 0 and res.stdout.strip():
                    # Забираем только первую строку, если интерфейс имеет несколько IP
                    first_line = res.stdout.strip().splitlines()[0]
                    if first_line.isdigit():
                        self.backup_interface_index = int(first_line)
                        print(f"[RouteManager] Системный индекс интерфейса {iface}: {self.backup_interface_index}")
                else:
                    self.backup_interface_index = None
            except Exception as e:
                print(f"[RouteManager] Ошибка получения IF Index: {e}")
                self.backup_interface_index = None
                
            return True
        print("[RouteManager] Не удалось найти дефолтный шлюз для бэкапа!")
        return False

    def _start_route_guard(self):
        import threading
        self._stop_guard = threading.Event()
        self._guard_thread = threading.Thread(target=self._route_guard_loop, daemon=True)
        self._guard_thread.start()

    def _route_guard_loop(self):
        import time
        while not self._stop_guard.is_set():
            time.sleep(3)
            if not self._is_modified or not self._last_server_ip:
                break
                
            # Проверяем, существует ли еще обходной маршрут до сервера в таблице
            route_exists = False
            try:
                # Ищем упоминание IP сервера в результатах route print
                output = subprocess.check_output(f"route print {self._last_server_ip}", shell=True, text=True)
                if self._last_server_ip in output and self.backup_gateway in output:
                    route_exists = True
            except Exception:
                pass
                
            if not route_exists:
                # Если маршрут пропал (был ресет интерфейса/кабеля) - восстанавливаем!
                print(f"[RouteManager] Обнаружена пропажа обходного маршрута для {self._last_server_ip}! Восстановление...")
                
                # Переопределяем шлюз (на случай, если DHCP выдал другой IP/шлюз при переподключении)
                gw, _ = self.get_default_gateway()
                if gw:
                    self.backup_gateway = gw
                
                if self.backup_gateway:
                    subprocess.run(
                        f"route add {self._last_server_ip} mask 255.255.255.255 {self.backup_gateway} metric 1",
                        shell=True, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    )

    def setup_tun_routes(self, tun_gateway: str, server_ip: str) -> bool:
        if not self.backup_routes():
            return False

        try:
            if server_ip and self.backup_gateway:
                subprocess.run(
                    f"route add {server_ip} mask 255.255.255.255 {self.backup_gateway} metric 1",
                    shell=True, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                print(f"[RouteManager] Добавлен обходной маршрут для сервера: {server_ip} -> {self.backup_gateway}")

            # Глобальные маршруты 0.0.0.0 и 128.0.0.0 теперь устанавливает сам sing-box (auto_route: True),
            # Мы их не дублируем, чтобы избежать конфликтов в таблице Windows.
            
            self._is_modified = True
            self._last_server_ip = server_ip
            
            # Запускаем фоновый мониторинг маршрутов для защиты от разрыва кабеля
            self._start_route_guard()
            
            print(f"[RouteManager] Маршруты успешно перенаправлены на TUN: {tun_gateway}")
            return True
        except Exception as e:
            print(f"[RouteManager] Ошибка установки TUN маршрутов: {e}")
            self.restore_routes()
            return False

    def restore_routes(self) -> None:
        if hasattr(self, "_stop_guard") and self._stop_guard:
            self._stop_guard.set()

        # Аварийная зачистка системного прокси на случай сбоев прошлых версий
        try:
            import winreg
            import ctypes
            internet_settings = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r'Software\Microsoft\Windows\CurrentVersion\Internet Settings',
                0, winreg.KEY_ALL_ACCESS
            )
            winreg.SetValueEx(internet_settings, "ProxyEnable", 0, winreg.REG_DWORD, 0)
            winreg.CloseKey(internet_settings)
            ctypes.windll.wininet.InternetSetOptionW(0, 39, 0, 0)
            ctypes.windll.wininet.InternetSetOptionW(0, 37, 0, 0)
            print("[RouteManager] Системный прокси Windows сброшен в исходное состояние.")
        except Exception:
            pass

        if not self._is_modified:
            self.backup_gateway = None
            self.backup_interface = None
            self.backup_interface_index = None
            self._last_server_ip = None
            return

        print("[RouteManager] Восстановление таблицы маршрутизации...")
        try:
            last_server_ip = getattr(self, "_last_server_ip", None)
            if last_server_ip:
                subprocess.run(f"route delete {last_server_ip}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            print("[RouteManager] Обходные маршруты удалены. Сетевое подключение переключено на физический адаптер.")
        except Exception as e:
            print(f"[RouteManager] Критическая ошибка при восстановлении маршрутов: {e}")
        finally:
            self._is_modified = False
            self.backup_gateway = None
            self.backup_interface = None
            self._last_server_ip = None