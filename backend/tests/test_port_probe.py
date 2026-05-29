"""Tests for the port-probe helper (backend/app/port_probe.py)."""

import socket

import pytest

from app.port_probe import find_free_port


def test_find_free_port_skips_occupied_port() -> None:
    """Occupy the first free port in range, then assert helper returns a different one."""
    first_free: int | None = None
    for port in range(8000, 8011):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                first_free = port
                break
        except OSError:
            continue

    if first_free is None:
        pytest.skip("No port in 8000-8010 is free on this machine")

    occupied = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        occupied.bind(("127.0.0.1", first_free))
        result = find_free_port()
        assert result is not None, "No free port found in 8000-8010 while one should exist"
        assert result != first_free, (
            f"find_free_port returned {result} but port {first_free} was occupied"
        )
        assert 8000 <= result <= 8010, f"Port {result} is outside the expected range 8000-8010"
    finally:
        occupied.close()
