"""Interfaz que debe cumplir cada plataforma (software de panel) de MKP."""
from dataclasses import dataclass, field


class ErrorAlta(Exception):
    """Fallo al dar de alta un proveedor (el mensaje va a Observaciones)."""


@dataclass
class ResultadoAlta:
    advertencias: list = field(default_factory=list)   # se guardó pero hay algo que revisar


@dataclass
class ProveedorEnSitio:
    nombre: str
    direccion: str = ""
    pestana: str = ""


class Plataforma:
    """Cada MKP nuevo con un panel distinto implementa estos métodos."""

    def __init__(self, page, base_url: str, log, diag_dir):
        self.page = page
        self.base_url = base_url
        self.log = log
        self.diag_dir = diag_dir

    def login(self, usuario: str, password: str) -> None:
        raise NotImplementedError

    def buscar(self, nombre: str) -> "ProveedorEnSitio | None":
        """Busca un proveedor por nombre exacto en el panel."""
        raise NotImplementedError

    def alta(self, proveedor) -> ResultadoAlta:
        """Crea el proveedor. Lanza ErrorAlta si no se pudo guardar."""
        raise NotImplementedError

    def diagnosticar(self, proveedor_ejemplo) -> None:
        """Vuelca HTML/capturas para ajustar selectores, sin guardar nada."""
        raise NotImplementedError
