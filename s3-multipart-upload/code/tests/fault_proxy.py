"""A TCP relay that can break an upload partway, to act out a bad connection."""

import socket
import threading

# The SDK's API calls are far smaller than this, and a part upload is far larger.
LARGE_REQUEST_BYTES = 1024 * 1024


def _shut(connection: socket.socket, how: int = socket.SHUT_RDWR) -> None:
    try:
        connection.shutdown(how)
    except OSError:
        pass  # already closed


def _copy_replies(source: socket.socket, sink: socket.socket) -> None:
    try:
        while data := source.recv(65536):
            sink.sendall(data)
    except OSError:
        pass  # one side went away
    finally:
        _shut(sink, socket.SHUT_WR)


class FaultProxy:
    """Relays bytes to the emulator. TLS and request signatures pass through unchanged.

    After arm("drop", 2), the second large upload is cut off after about 1 MiB.
    With "stall", the rest of it is swallowed and no reply comes, so a test can
    interrupt the uploader in the middle of a part.
    """

    def __init__(self, target_port: int):
        self.target = ("127.0.0.1", target_port)
        self.listener = socket.create_server(("127.0.0.1", 0))
        self.endpoint = f"https://127.0.0.1:{self.listener.getsockname()[1]}"
        self.tripped = threading.Event()
        self._lock = threading.Lock()
        self._fault: str | None = None
        self._countdown = 0
        threading.Thread(target=self._accept, daemon=True).start()

    def arm(self, fault: str, upload_number: int) -> None:
        assert fault in ("drop", "stall")
        self._fault, self._countdown = fault, upload_number

    def close(self) -> None:
        _shut(self.listener)
        self.listener.close()

    def _accept(self) -> None:
        while True:
            try:
                client, _ = self.listener.accept()
            except OSError:
                return  # the proxy was closed
            threading.Thread(target=self._relay, args=(client,), daemon=True).start()

    def _count_large_upload(self) -> str | None:
        """Return the fault if this is the upload it was armed for."""
        with self._lock:
            self._countdown -= 1
            return self._fault if self._countdown == 0 else None

    def _relay(self, client: socket.socket) -> None:
        with client, socket.create_connection(self.target) as server:
            replies = threading.Thread(target=_copy_replies, args=(server, client), daemon=True)
            replies.start()
            received, counted = 0, False
            try:
                while data := client.recv(65536):
                    received += len(data)
                    if received > LARGE_REQUEST_BYTES and not counted:
                        counted = True
                        if fault := self._count_large_upload():
                            self.tripped.set()
                            if fault == "stall":
                                while client.recv(65536):
                                    pass  # wait until the uploader goes away
                            break
                    server.sendall(data)
            except OSError:
                pass  # one side went away
            finally:
                _shut(client)
                _shut(server)
                replies.join()
