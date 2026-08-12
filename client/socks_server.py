import asyncio
import socket
import logging
import ipaddress
import time
import traceback
from typing import Dict, Any

from common.config import load_users_jsonl, validate_credentials
from common.socks5 import (
    SOCKS_VERSION, METHOD_NO_AUTH, METHOD_USER_PASS, METHOD_NO_ACCEPTABLE,
    CMD_CONNECT, CMD_UDP_ASSOCIATE,
    REP_SUCCESS, REP_GENERAL_FAILURE, REP_CMD_NOT_SUPPORTED,
    read_socks_address, pack_socks_address, pack_udp_packet
)
from common.tunnel import (
    PTCPStream, send_tunnel_cmd_request, read_tunnel_cmd_response,
    send_udp_frame, read_udp_frame
)
from client.aptcp_client import APTCPTunnelClient

logger = logging.getLogger("SOCKS5Client")

try:
    from src.network.process_finder import ProcessFinder
except ImportError:
    ProcessFinder = None


import logging.handlers
import queue


def _setup_whitelist_logger(log_file="whitelist_debug.log"):
    wl_log = logging.getLogger("WhitelistDebug")
    wl_log.setLevel(logging.CRITICAL)
    wl_log.propagate = False

    for h in list(wl_log.handlers):
        wl_log.removeHandler(h)

    wl_log.addHandler(logging.NullHandler())
    return wl_log

wl_logger = _setup_whitelist_logger()


class SOCKS5Server:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.socks_host = config.get("socks_host", "127.0.0.1")
        self.socks_port = int(config.get("socks_port", 1080))
        self.auth_enabled = config.get("auth_enabled", False)
        self.users_file = config.get("users_file", "client/users.jsonl")
        self.users = load_users_jsonl(self.users_file) if self.auth_enabled else {}

        self.aptcp_host = config.get("aptcp_server_host", "127.0.0.1")
        self.aptcp_port = int(config.get("aptcp_server_port", 9090))
        self.aptcp_auth_enabled = config.get("aptcp_auth_enabled", False)
        self.aptcp_username = config.get("aptcp_username", "")
        self.aptcp_password = config.get("aptcp_password", "")
        self.aptcp_tls_enabled = config.get("aptcp_tls_enabled", False)
        self.aptcp_tls_ca_cert = config.get("aptcp_tls_ca_cert", None)
        self.timeout = int(config.get("timeout", 30))

        self._server = None

    async def start(self):
        self._server = await asyncio.start_server(
            self.handle_client, self.socks_host, self.socks_port, reuse_address=True
        )
        logger.info(f"Local SOCKS5 Server listening on {self.socks_host}:{self.socks_port}")

    async def serve_forever(self):
        if self._server:
            await self._server.serve_forever()

    async def close(self):
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        sock = writer.get_extra_info('socket')
        if sock:
            try:
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except Exception:
                pass
        try:
            # 1. Greeting & Method Negotiation
            header = await reader.readexactly(2)
            ver, nmethods = header[0], header[1]
            if ver != SOCKS_VERSION:
                writer.close()
                await writer.wait_closed()
                return

            methods = await reader.readexactly(nmethods)

            if self.auth_enabled:
                if METHOD_USER_PASS not in methods:
                    writer.write(bytes([SOCKS_VERSION, METHOD_NO_ACCEPTABLE]))
                    await writer.drain()
                    writer.close()
                    await writer.wait_closed()
                    return

                writer.write(bytes([SOCKS_VERSION, METHOD_USER_PASS]))
                await writer.drain()

                # Perform RFC 1929 Auth Subnegotiation
                auth_ver = (await reader.readexactly(1))[0]
                u_len = (await reader.readexactly(1))[0]
                username = (await reader.readexactly(u_len)).decode('utf-8', errors='ignore')
                p_len = (await reader.readexactly(1))[0]
                password = (await reader.readexactly(p_len)).decode('utf-8', errors='ignore')

                if not validate_credentials(self.users, username, password):
                    logger.warning(f"SOCKS5 auth failed for user: {username}")
                    writer.write(bytes([auth_ver, 0x01]))
                    await writer.drain()
                    writer.close()
                    await writer.wait_closed()
                    return

                writer.write(bytes([auth_ver, 0x00]))
                await writer.drain()
            else:
                if METHOD_NO_AUTH not in methods:
                    writer.write(bytes([SOCKS_VERSION, METHOD_NO_ACCEPTABLE]))
                    await writer.drain()
                    writer.close()
                    await writer.wait_closed()
                    return
                writer.write(bytes([SOCKS_VERSION, METHOD_NO_AUTH]))
                await writer.drain()

            # 2. Command Request
            req_header = await reader.readexactly(2)
            _, cmd = req_header[0], req_header[1]
            _ = await reader.readexactly(1)  # RSV
            atyp, target_host, target_port, _ = await read_socks_address(reader.readexactly)

            peer_info = writer.get_extra_info('peername')
            client_ip, client_port = peer_info if peer_info and len(peer_info) >= 2 else ("127.0.0.1", 0)

            proc_pid, proc_name = None, None
            if ProcessFinder and client_port:
                try:
                    loop = asyncio.get_running_loop()
                    proc_pid, proc_name = await loop.run_in_executor(
                        None, ProcessFinder.get_pid_and_name_by_local_port, client_port
                    )
                except Exception:
                    pass

            proc_str = f"{proc_name} (PID: {proc_pid})" if proc_name and proc_pid else (proc_name or (f"PID: {proc_pid}" if proc_pid else "Неизвестный процесс"))

            cmd_name = "CONNECT" if cmd == CMD_CONNECT else ("UDP_ASSOC" if cmd == CMD_UDP_ASSOCIATE else f"CMD_{cmd}")
            wl_logger.info(
                f"===> [ВХОДЯЩИЙ ЗАПРОС ПРИЛОЖЕНИЯ]\n"
                f"  • Процесс:    {proc_str}\n"
                f"  • Сокет:      {client_ip}:{client_port}\n"
                f"  • Команда:    SOCKS5 {cmd_name} (0x{cmd:02x})\n"
                f"  • Назначение: {target_host}:{target_port} (ATYP: {atyp})"
            )

            if cmd not in (CMD_CONNECT, CMD_UDP_ASSOCIATE):
                wl_logger.warning(f"❌ [ОТКЛОНЕНО] Процесс {proc_str}: команда {cmd_name} не поддерживается!")
                rep_bytes = bytes([SOCKS_VERSION, REP_CMD_NOT_SUPPORTED, 0x00]) + pack_socks_address("0.0.0.0", 0)
                writer.write(rep_bytes)
                await writer.drain()
                writer.close()
                await writer.wait_closed()
                return

            # Локальное разрешение доменного имени перед отправкой в туннель
            resolved_target = target_host
            is_domain = False
            try:
                ipaddress.ip_address(target_host)
            except ValueError:
                is_domain = True
                try:
                    loop = asyncio.get_running_loop()
                    infos = await asyncio.wait_for(
                        loop.getaddrinfo(target_host, target_port, family=socket.AF_INET, type=socket.SOCK_STREAM),
                        timeout=3.0
                    )
                    if infos and len(infos) > 0:
                        resolved_target = infos[0][4][0]
                        wl_logger.info(f"  • DNS-резолв: Домен '{target_host}' для {proc_str} разрешен локально -> {resolved_target}")
                except Exception as dns_err:
                    wl_logger.warning(f"  • DNS-резолв: Не удалось разрешить '{target_host}' локально ({dns_err}), отправляется оригинальный хост.")

            # Для CMD_CONNECT отправляем МГНОВЕННЫЙ SOCKS5 ACK (0x00 SUCCESS) клиенту (< 0.1 мс)
            if cmd == CMD_CONNECT:
                rep_bytes = bytes([SOCKS_VERSION, REP_SUCCESS, 0x00]) + pack_socks_address("0.0.0.0", 0)
                writer.write(rep_bytes)
                await writer.drain()
                wl_logger.info(f"  • [EARLY ACK] Мгновенный SOCKS5 0x00 SUCCESS отправлен процессу {proc_str} для {target_host}:{target_port}")

            # 3. Фоновое подключение к APTCP Серверу
            wl_logger.info(f"  • [APTCP СВЯЗЬ] Создание PTCPStream к шлюзу {self.aptcp_host}:{self.aptcp_port} (TLS={self.aptcp_tls_enabled}) для {proc_str}...")
            t_conn_start = time.time()
            tunnel_client = APTCPTunnelClient(
                self.aptcp_host, 
                self.aptcp_port, 
                timeout=self.timeout,
                tls_enabled=self.aptcp_tls_enabled, 
                tls_ca_cert=self.aptcp_tls_ca_cert
            )
            try:
                ptcp_stream = await tunnel_client.connect_and_authenticate(
                    self.aptcp_auth_enabled, self.aptcp_username, self.aptcp_password
                )
                t_conn_dur = (time.time() - t_conn_start) * 1000
                wl_logger.info(f"  • [APTCP АВТОРИЗАЦИЯ] Авторизация успешна за {t_conn_dur:.1f} мс к {self.aptcp_host}:{self.aptcp_port}")
            except Exception as e:
                wl_logger.error(
                    f"❌ [APTCP ОШИБКА] Не удалось подключиться или авторизоваться на {self.aptcp_host}:{self.aptcp_port}\n"
                    f"  • Процесс: {proc_str}\n"
                    f"  • Цель: {target_host}:{target_port}\n"
                    f"  • Ошибка: {e}\n{traceback.format_exc()}"
                )
                if cmd != CMD_CONNECT:
                    rep_bytes = bytes([SOCKS_VERSION, REP_GENERAL_FAILURE, 0x00]) + pack_socks_address("0.0.0.0", 0)
                    writer.write(rep_bytes)
                    await writer.drain()
                writer.close()
                await writer.wait_closed()
                return

            # 4. Пересылка SOCKS-команды в туннель
            wl_logger.info(f"  • [ТУННЕЛЬ КОМАНДА] Отправка CMD_{cmd_name} к {resolved_target}:{target_port} через туннель...")
            try:
                await send_tunnel_cmd_request(ptcp_stream, cmd, resolved_target, target_port)
            except Exception as e:
                wl_logger.error(
                    f"❌ [ТУННЕЛЬ ОШИБКА] Сбой отправки команды туннеля для {proc_str} ({target_host}:{target_port}): {e}\n"
                    f"{traceback.format_exc()}"
                )
                if cmd != CMD_CONNECT:
                    rep_bytes = bytes([SOCKS_VERSION, REP_GENERAL_FAILURE, 0x00]) + pack_socks_address("0.0.0.0", 0)
                    writer.write(rep_bytes)
                    await writer.drain()
                await ptcp_stream.close()
                writer.close()
                await writer.wait_closed()
                return

            if cmd == CMD_UDP_ASSOCIATE:
                try:
                    rep, _, bnd_host, bnd_port = await asyncio.wait_for(
                        read_tunnel_cmd_response(ptcp_stream),
                        timeout=10.0
                    )
                    if rep != REP_SUCCESS:
                        wl_logger.error(f"❌ [СЕРВЕР ОТКЛОНИЛ UDP] APTCP сервер вернул ошибку rep=0x{rep:02x} для {proc_str}")
                        rep_bytes = bytes([SOCKS_VERSION, rep, 0x00]) + pack_socks_address("0.0.0.0", 0)
                        writer.write(rep_bytes)
                        await writer.drain()
                        await ptcp_stream.close()
                        writer.close()
                        await writer.wait_closed()
                        return
                except Exception as e:
                    wl_logger.error(f"❌ [UDP ТУННЕЛЬ ОШИБКА] {e}")
                    await ptcp_stream.close()
                    writer.close()
                    await writer.wait_closed()
                    return

                udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                udp_sock.bind((self.socks_host, 0))
                udp_sock.setblocking(False)
                local_bnd_host, local_bnd_port = udp_sock.getsockname()

                rep_bytes = bytes([SOCKS_VERSION, REP_SUCCESS, 0x00]) + pack_socks_address(local_bnd_host, local_bnd_port)
                writer.write(rep_bytes)
                await writer.drain()

                await self._relay_udp(reader, writer, udp_sock, ptcp_stream, proc_str)

            elif cmd == CMD_CONNECT:
                wl_logger.info(f"✅ [TCP СЕССИЯ СТАРТ] Процесс {proc_str} -> {target_host} ({resolved_target}:{target_port})")
                await self._relay_tcp_logged(reader, writer, ptcp_stream, target_host, resolved_target, target_port, proc_str)

        except (asyncio.IncompleteReadError, ConnectionResetError):
            pass
        except Exception as e:
            logger.error(f"Error handling SOCKS client: {e}")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _relay_tcp_logged(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        ptcp_stream: PTCPStream,
        orig_host: str = "unknown",
        target_ip: str = "0.0.0.0",
        target_port: int = 0,
        proc_str: str = "Неизвестный процесс"
    ):
        """Параллельная ретрансляция TCP с зачитыванием ответа туннеля и передачей данных клиента без задержек."""
        bytes_sent = 0
        bytes_recv = 0
        start_relay_time = time.time()

        async def client_to_ptcp():
            nonlocal bytes_sent
            try:
                while True:
                    data = await reader.read(65536)
                    if not data:
                        break
                    bytes_sent += len(data)
                    await ptcp_stream.send(data)
            except Exception:
                pass

        async def ptcp_to_client():
            nonlocal bytes_recv
            try:
                # Читаем ответ о статусе подключения туннеля с таймаутом 20 секунд
                rep, _, bnd_host, bnd_port = await asyncio.wait_for(
                    read_tunnel_cmd_response(ptcp_stream),
                    timeout=20.0
                )
                if rep != REP_SUCCESS:
                    wl_logger.error(f"❌ [СЕРВЕР ОТКЛОНИЛ] APTCP сервер вернул ошибку rep=0x{rep:02x} для {proc_str} -> {orig_host}:{target_port}")
                    return

                wl_logger.info(f"  • [ТУННЕЛЬ ПОДТВЕРЖДЕН] Связанный адрес={bnd_host}:{bnd_port} для {proc_str}")

                while True:
                    data = await ptcp_stream.read(65536)
                    if not data:
                        break
                    bytes_recv += len(data)
                    writer.write(data)
                    await writer.drain()
            except asyncio.TimeoutError:
                wl_logger.error(f"⏱️ [ТАЙМАУТ ЦЕЛЕВОГО ХОСТА] Сервер {orig_host}:{target_port} не ответил за 20 секунд (хост недоступен или заблокирован).")
            except Exception:
                pass

        t1 = asyncio.create_task(client_to_ptcp())
        t2 = asyncio.create_task(ptcp_to_client())

        try:
            done, pending = await asyncio.wait([t1, t2], return_when=asyncio.FIRST_COMPLETED)
        finally:
            for t in [t1, t2]:
                t.cancel()
            await asyncio.gather(t1, t2, return_exceptions=True)

        await ptcp_stream.close()
        duration = time.time() - start_relay_time
        total_bytes = bytes_sent + bytes_recv
        avg_speed = (total_bytes / duration / 1024) if duration > 0 else 0

        wl_logger.info(
            f"🏁 [TCP СЕССИЯ ЗАВЕРШЕНА]\n"
            f"  • Процесс:     {proc_str}\n"
            f"  • Назначение:  {orig_host} ({target_ip}:{target_port})\n"
            f"  • Длительность:{duration:.2f} сек\n"
            f"  • Отправлено:  {bytes_sent:,} байт ({bytes_sent / 1024:.2f} KB)\n"
            f"  • Получено:    {bytes_recv:,} байт ({bytes_recv / 1024:.2f} KB)\n"
            f"  • Всего:       {total_bytes:,} байт ({total_bytes / 1024:.2f} KB)\n"
            f"  • Ср. скорость:{avg_speed:.2f} KB/s"
        )

    async def _relay_tcp(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, ptcp_stream: PTCPStream):
        await self._relay_tcp_logged(reader, writer, ptcp_stream, "unknown", "0.0.0.0", 0)

    async def _relay_udp(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        udp_sock: socket.socket,
        ptcp_stream: PTCPStream,
        proc_str: str = "Неизвестный процесс"
    ):
        """Ретрансляция UDP между локальным сокетом и APTCP-потоком с детальной статистикой."""
        loop = asyncio.get_running_loop()
        proxifier_udp_addr = None
        addr_event = asyncio.Event()
        bytes_sent = 0
        bytes_recv = 0
        packets_sent = 0
        packets_recv = 0
        start_time = time.time()

        async def udp_to_ptcp():
            nonlocal proxifier_udp_addr, bytes_sent, packets_sent
            try:
                while True:
                    data, addr = await loop.sock_recvfrom(udp_sock, 65536)
                    if not proxifier_udp_addr:
                        proxifier_udp_addr = addr
                        addr_event.set()
                    bytes_sent += len(data)
                    packets_sent += 1
                    await send_udp_frame(ptcp_stream, data)
            except Exception:
                pass

        async def ptcp_to_udp():
            nonlocal bytes_recv, packets_recv
            try:
                await addr_event.wait()
                while True:
                    frame = await read_udp_frame(ptcp_stream)
                    if proxifier_udp_addr and frame:
                        if len(frame) >= 10 and frame[0] == 0 and frame[1] == 0:
                            out_packet = frame
                        else:
                            out_packet = pack_udp_packet("0.0.0.0", 0, frame)
                        bytes_recv += len(out_packet)
                        packets_recv += 1
                        await loop.sock_sendto(udp_sock, out_packet, proxifier_udp_addr)
            except Exception:
                pass

        async def monitor_tcp_control():
            try:
                while True:
                    data = await reader.read(1)
                    if not data:
                        break
            except Exception:
                pass

        t_udp_in = asyncio.create_task(udp_to_ptcp())
        t_udp_out = asyncio.create_task(ptcp_to_udp())
        t_tcp_ctrl = asyncio.create_task(monitor_tcp_control())

        tasks = [t_udp_in, t_udp_out, t_tcp_ctrl]
        wl_logger.info(f"✅ [UDP СЕССИЯ СТАРТ] Процесс {proc_str}")
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        try:
            udp_sock.close()
        except Exception:
            pass

        await ptcp_stream.close()
        duration = time.time() - start_time
        total_bytes = bytes_sent + bytes_recv

        wl_logger.info(
            f"🏁 [UDP СЕССИЯ ЗАВЕРШЕНА]\n"
            f"  • Процесс:     {proc_str}\n"
            f"  • Длительность:{duration:.2f} сек\n"
            f"  • Отправлено:  {packets_sent} пакетов ({bytes_sent:,} байт / {bytes_sent / 1024:.2f} KB)\n"
            f"  • Получено:    {packets_recv} пакетов ({bytes_recv:,} байт / {bytes_recv / 1024:.2f} KB)\n"
            f"  • Всего:       {total_bytes:,} байт ({total_bytes / 1024:.2f} KB)"
        )