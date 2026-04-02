"""Transport layer with length-prefixed framing (Unix socket + Named pipe)."""

from __future__ import annotations

import logging
import os
import platform
import socket
import struct
import threading
from typing import Callable, Optional

from .message import BusMessage


UNIX_SOCKET_PATH = "/tmp/clevrr_bus.sock"
WIN_PIPE_NAME = "\\\\.\\pipe\\clevrr_bus"
HEADER_SIZE = 4
MAX_MSG_SIZE = 1024 * 1024
RECV_BUFFER = 65536


def frame(data: bytes) -> bytes:
    """Pack 4-byte length header + data."""
    return struct.pack(">I", len(data)) + data


def recv_framed(sock: socket.socket) -> Optional[bytes]:
    """Receive length-prefixed message."""
    header = _recv_exact(sock, HEADER_SIZE)
    if not header:
        return None
    length = struct.unpack(">I", header)[0]
    if length > MAX_MSG_SIZE:
        raise ValueError(f"Message too large: {length}")
    return _recv_exact(sock, length)


def _recv_exact(sock: socket.socket, n: int) -> Optional[bytes]:
    """Receive exactly n bytes from socket."""
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(min(n - len(buf), RECV_BUFFER))
        if not chunk:
            return None
        buf.extend(chunk)
    return bytes(buf)


class TransportServer:
    """Socket/pipe server with length-prefixed framing."""

    def __init__(
        self,
        on_message: Callable[[BusMessage, socket.socket], None],
    ) -> None:
        """Initialize transport server."""
        self._on_message = on_message
        self._is_windows = platform.system() == "Windows"
        self._stop_event = threading.Event()
        self._server_sock: Optional[socket.socket] = None
        self._threads: list[threading.Thread] = []
        self.logger = logging.getLogger("clevrr.bus.transport")

    def start(self) -> None:
        """Start transport server."""
        target = (
            self._run_named_pipe if self._is_windows
            else self._run_unix_socket
        )
        t = threading.Thread(
            target=target,
            name="clevrr-bus-transport",
            daemon=True,
        )
        self._threads.append(t)
        t.start()

    def stop(self) -> None:
        """Stop transport server."""
        self._stop_event.set()
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass
        
        if not self._is_windows:
            try:
                os.unlink(UNIX_SOCKET_PATH)
            except FileNotFoundError:
                pass

    def send(self, sock: socket.socket, msg: BusMessage) -> None:
        """Send message to client."""
        data = msg.to_bytes()
        sock.sendall(frame(data))

    def _run_unix_socket(self) -> None:
        """Unix socket server loop."""
        try:
            os.unlink(UNIX_SOCKET_PATH)
        except FileNotFoundError:
            pass

        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(UNIX_SOCKET_PATH)
        os.chmod(UNIX_SOCKET_PATH, 0o600)
        server.listen(10)
        server.settimeout(1.0)
        self._server_sock = server

        self.logger.info(f"Bus socket listening at {UNIX_SOCKET_PATH}")

        while not self._stop_event.is_set():
            try:
                conn, _ = server.accept()
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                t = threading.Thread(
                    target=self._handle_client,
                    args=(conn,),
                    daemon=True,
                )
                self._threads.append(t)
                t.start()
            except socket.timeout:
                continue
            except Exception as exc:
                if not self._stop_event.is_set():
                    self.logger.error(f"Accept error: {exc}")

    def _run_named_pipe(self) -> None:
        """Windows named pipe server loop."""
        try:
            import win32pipe
            import win32file
            import pywintypes

            self.logger.info(f"Bus named pipe listening at {WIN_PIPE_NAME}")

            while not self._stop_event.is_set():
                try:
                    pipe = win32pipe.CreateNamedPipe(
                        WIN_PIPE_NAME,
                        win32pipe.PIPE_ACCESS_DUPLEX,
                        (win32pipe.PIPE_TYPE_MESSAGE |
                         win32pipe.PIPE_READMODE_MESSAGE),
                        win32pipe.PIPE_UNLIMITED_INSTANCES,
                        MAX_MSG_SIZE,
                        MAX_MSG_SIZE,
                        0,
                        None,
                    )
                    win32pipe.ConnectNamedPipe(pipe, None)
                    t = threading.Thread(
                        target=self._handle_windows_client,
                        args=(pipe,),
                        daemon=True,
                    )
                    self._threads.append(t)
                    t.start()
                except Exception as exc:
                    if not self._stop_event.is_set():
                        self.logger.error(f"Pipe error: {exc}")

        except ImportError:
            self.logger.error(
                "pywin32 not installed — named pipe unavailable"
            )

    def _handle_client(self, conn: socket.socket) -> None:
        """Handle Unix socket client."""
        try:
            conn.settimeout(30.0)
            while not self._stop_event.is_set():
                data = recv_framed(conn)
                if data is None:
                    break
                msg = BusMessage.from_bytes(data)
                self._on_message(msg, conn)
        except Exception as exc:
            self.logger.debug(f"Client error: {exc}")
        finally:
            conn.close()

    def _handle_windows_client(self, pipe) -> None:
        """Handle Windows named pipe client."""
        try:
            import win32file

            while not self._stop_event.is_set():
                _, data = win32file.ReadFile(pipe, MAX_MSG_SIZE)
                msg = BusMessage.from_bytes(data)
                self._on_message(msg, pipe)
        except Exception:
            pass
        finally:
            try:
                import win32pipe
                win32pipe.DisconnectNamedPipe(pipe)
                import win32file
                win32file.CloseHandle(pipe)
            except Exception:
                pass
