"""Carga de .env y obtención de URL / usuario / contraseña de cada MKP."""
import getpass
import os

from config import MARKETPLACES, RAIZ


def cargar_dotenv() -> None:
    """Lee RAIZ/.env sin dependencias externas. Las variables de entorno ya
    definidas (p. ej. con `set` en cmd) tienen prioridad sobre el archivo."""
    env_path = RAIZ / ".env"
    if not env_path.is_file():
        return
    for linea in env_path.read_text(encoding="utf-8-sig").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        k, v = linea.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def tiene_credenciales(clave: str) -> bool:
    return bool(os.environ.get(f"MKP_{clave}_USUARIO") and os.environ.get(f"MKP_{clave}_PASSWORD"))


def credenciales(clave: str) -> tuple[str, str, str]:
    """Devuelve (url, usuario, password). Si faltan en .env, las pide por consola."""
    mkp = MARKETPLACES[clave]
    url = (os.environ.get(f"MKP_{clave}_URL") or mkp["url"]).rstrip("/")
    usuario = os.environ.get(f"MKP_{clave}_USUARIO", "")
    password = os.environ.get(f"MKP_{clave}_PASSWORD", "")
    if not usuario:
        usuario = input(f"Usuario/correo de {mkp['nombre']}: ").strip()
    if not password:
        password = getpass.getpass(f"Contraseña de {mkp['nombre']} (no se muestra): ")
    if not usuario or not password:
        raise SystemExit(f"Faltan credenciales para {clave}. Defínelas en .env "
                         f"(MKP_{clave}_USUARIO / MKP_{clave}_PASSWORD).")
    return url, usuario, password
