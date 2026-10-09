import socket

import pytest

from interfaz import fuentes, rutas
from interfaz.aplicacion import Aplicacion


@pytest.fixture(scope="session")
def corpus():
    """Los datos de ejemplo sintéticos: los mismos que usa el núcleo en sus pruebas."""
    return fuentes.cargar("ejemplo")


@pytest.fixture
def aplicacion(corpus, tmp_path, monkeypatch):
    """Una aplicación con su registro de revisión en una carpeta temporal."""
    monkeypatch.setattr(rutas, "ESTADO", tmp_path / "estado")
    return Aplicacion(corpus)


@pytest.fixture
def sin_internet(monkeypatch):
    """Hace fallar cualquier intento de abrir una conexión."""
    def bloquear(*argumentos, **opciones):
        raise AssertionError("La interfaz intentó usar la red.")

    monkeypatch.setattr(socket, "socket", bloquear)
    monkeypatch.setattr(socket, "create_connection", bloquear)
    monkeypatch.setattr(socket, "getaddrinfo", bloquear)
