import socket


def find_free_port(start: int = 8000, end: int = 8010) -> int | None:
    """Return the first TCP port in [start, end] bindable on 127.0.0.1, or None."""
    for port in range(start, end + 1):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return port
        except OSError:
            pass
    return None
