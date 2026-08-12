import psutil
from typing import Optional, Dict, Tuple

class ProcessFinder:
    """Утилита для определения имени исполняемого файла процесса по его PID."""
    
    _cache: Dict[int, str] = {}

    @classmethod
    def get_process_name(cls, pid: int) -> Optional[str]:
        # Защита от утечек памяти: сбрасываем кэш, если накопилось много мертвых PID
        if len(cls._cache) > 2000:
            cls._cache.clear()

        if pid in cls._cache:
            return cls._cache[pid]

        try:
            proc = psutil.Process(pid)
            name = proc.name()
            cls._cache[pid] = name
            return name
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return None

    # Кэш соответствия IP-адресов именам процессов: IP_str -> (process_name, timestamp)
    _ip_to_proc_cache: dict = {}
    # Снижаем время кэширования до 0.5 сек. Этого достаточно для обработки пачки параллельных
    # соединений от одной программы (всплеск при загрузке страницы), но исключает "залипание" IP
    # за процессом при переключении на другой браузер.
    _cache_duration = 0.5

    # Глобальный кэш таблицы сетевых соединений ОС
    _global_connections_cache = None
    _global_connections_timestamp = 0.0
    _global_cache_lifetime = 1.0  # Обновляем таблицу не чаще чем раз в 1 секунду
    _last_force_refresh_time = 0.0
    _find_lock = None

    @classmethod
    async def find_process_by_destination_async(cls, host: str, port: int) -> Optional[str]:
        """Асинхронный поиск процесса с использованием Executor и негативным кэшированием."""
        import asyncio
        import time

        if cls._find_lock is None:
            cls._find_lock = asyncio.Lock()

        now = time.time()
        # 1. Пытаемся получить из быстрого кэша по IP (включая негативный кэш "unknown")
        if host in cls._ip_to_proc_cache:
            proc_name, timestamp = cls._ip_to_proc_cache[host]
            if now - timestamp < cls._cache_duration:
                return None if proc_name == "unknown" else proc_name

        # Синхронизируем доступ к тяжелой операции сканирования сокетов
        async with cls._find_lock:
            # Повторная проверка кэша после захвата блокировки
            if host in cls._ip_to_proc_cache:
                proc_name, timestamp = cls._ip_to_proc_cache[host]
                if time.time() - timestamp < cls._cache_duration:
                    return None if proc_name == "unknown" else proc_name

            # 2. Если нет в кэше, запускаем тяжелый поиск в фоновом пуле потоков
            loop = asyncio.get_running_loop()
            proc_name = await loop.run_in_executor(None, cls._sync_find_process, host, port)
            
            # 3. Кэшируем результат поиска
            if len(cls._ip_to_proc_cache) > 2000:
                cls._ip_to_proc_cache.clear()
                
            cache_val = proc_name if proc_name else "unknown"
            cls._ip_to_proc_cache[host] = (cache_val, time.time())
                
            return proc_name

    @classmethod
    def _sync_find_process(cls, host: str, port: int, local_port: Optional[int] = None) -> Optional[str]:
        """Синхронный (блокирующий) поиск, запускаемый в Executor с глобальным кэшем."""
        import socket
        import ipaddress
        import time

        target_ip_obj = None
        try:
            # Сначала проверяем, является ли хост готовым IP-адресом, чтобы избежать DNS-запроса в ОС
            target_ip_obj = ipaddress.ip_address(host)
        except Exception:
            try:
                resolved_ip = socket.gethostbyname(host)
                target_ip_obj = ipaddress.ip_address(resolved_ip)
            except Exception:
                pass

        def search_in_cache():
            if cls._global_connections_cache is None:
                return None

            # Если передан локальный порт, ищем точное совпадение по нему (это мгновенно и 100% надежно)
            if local_port is not None:
                for conn in cls._global_connections_cache:
                    if conn.laddr and conn.laddr.port == local_port:
                        if conn.pid:
                            name = cls.get_process_name(conn.pid)
                            if name:
                                return name
                return None

            matching_conns = [c for c in cls._global_connections_cache if c.raddr and c.raddr.port == port]
            for conn in matching_conns:
                conn_ip_str = conn.raddr.ip
                if conn_ip_str.startswith("::ffff:"):
                    conn_ip_str = conn_ip_str.replace("::ffff:", "")
                
                conn_ip_obj = None
                try:
                    conn_ip_obj = ipaddress.ip_address(conn_ip_str)
                except Exception:
                    pass

                ip_match = False
                if target_ip_obj and conn_ip_obj:
                    ip_match = (target_ip_obj == conn_ip_obj)
                elif host.lower() == conn.raddr.ip.lower():
                    ip_match = True

                if ip_match and conn.pid:
                    name = cls.get_process_name(conn.pid)
                    if name:
                        return name
            return None

        try:
            # 1. Сначала ищем в текущем глобальном кэше (это мгновенно и экономит ресурсы CPU)
            name = search_in_cache()
            if name:
                return name

            # 2. Если не нашли, возможно это абсолютно новое только что открытое соединение.
            # Делаем принудительное обновление кэша, но не чаще чем раз в 100 мс для защиты от перегрузки.
            now = time.time()
            if cls._global_connections_cache is None or (now - cls._last_force_refresh_time > 0.1):
                cls._global_connections_cache = psutil.net_connections(kind='tcp')
                cls._global_connections_timestamp = now
                cls._last_force_refresh_time = now
                
                # Ищем повторно в обновленном кэше
                name = search_in_cache()
                if name:
                    return name
        except Exception:
            pass

        return None

    @classmethod
    def get_pid_by_local_port_win32(cls, local_port: int) -> Optional[int]:
        """Мгновенный поиск PID по локальному порту TCP через Win32 API GetExtendedTcpTable (< 0.05 мс)."""
        import ctypes
        import socket
        from ctypes import wintypes

        try:
            iphlpapi = ctypes.windll.iphlpapi
            AF_INET = 2
            TCP_TABLE_OWNER_PID_ALL = 5
            
            size = wintypes.DWORD(0)
            iphlpapi.GetExtendedTcpTable(None, ctypes.byref(size), False, AF_INET, TCP_TABLE_OWNER_PID_ALL, 0)
            
            buffer = ctypes.create_string_buffer(size.value)
            if iphlpapi.GetExtendedTcpTable(buffer, ctypes.byref(size), False, AF_INET, TCP_TABLE_OWNER_PID_ALL, 0) == 0:
                num_entries = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ulong))[0]
                p_table = ctypes.cast(ctypes.addressof(buffer) + 4, ctypes.POINTER(ctypes.c_ulong * 6 * num_entries))
                
                target_port_net = socket.htons(local_port)
                
                for i in range(num_entries):
                    row = p_table.contents[i]
                    if row[2] == target_port_net:
                        return row[5]  # dwOwningPid
        except Exception:
            pass
        return None

    @classmethod
    def get_pid_and_name_by_local_port(cls, local_port: int) -> Tuple[Optional[int], Optional[str]]:
        """Сверхбыстрый поиск PID и имени процесса без задержек пакетов."""
        # 1. Пробуем прямой вызов Win32 API (< 0.05 мс)
        pid = cls.get_pid_by_local_port_win32(local_port)
        if pid:
            name = cls.get_process_name(pid)
            if name:
                return pid, name

        # 2. Фолбэк на psutil кэш
        if cls._global_connections_cache:
            for conn in cls._global_connections_cache:
                if conn.laddr and conn.laddr.port == local_port:
                    if conn.pid:
                        return conn.pid, cls.get_process_name(conn.pid)

        return None, None

    @classmethod
    def clear_cache(cls) -> None:
        cls._cache.clear()
        cls._ip_to_proc_cache.clear()