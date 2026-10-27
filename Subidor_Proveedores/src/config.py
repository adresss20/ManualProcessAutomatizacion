"""
Configuración general y registro de marketplaces (MKP).

Para agregar un MKP nuevo:
  1. Añade una entrada a MARKETPLACES (clave en MAYÚSCULAS, sin espacios).
  2. En .env define MKP_<CLAVE>_URL, MKP_<CLAVE>_USUARIO y MKP_<CLAVE>_PASSWORD.
  3. Si el panel es de otra plataforma (otro software), crea un módulo en
     src/plataformas/ y regístralo en PLATAFORMAS (src/plataformas/__init__.py).
"""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
OUTPUT_DIR = RAIZ / "output"
BACKUP_DIR = OUTPUT_DIR / "backups"
LOGS_DIR = RAIZ / "logs"
ERRORES_DIR = LOGS_DIR / "errores"

# Excel por defecto (si no existe, se usa el único .xlsx de la carpeta raíz).
EXCEL_DEFAULT = RAIZ / "Información_Proveedores.xlsx"

# ─────────────────────────────────────────────
#  Marketplaces
# ─────────────────────────────────────────────
# plataforma = módulo de automatización a usar. UNEFARM corre sobre el mismo
# software que Farmacias a Domicilio, por eso comparten la plataforma "fad".
MARKETPLACES = {
    "FAD": {
        "nombre": "Farmacias a Domicilio",
        "url": "https://farmaciasadomicilio.mx",
        "plataforma": "fad",
    },
    "UNEFARM": {
        "nombre": "UNEFARM",
        "url": "https://unefarm.farmaciasadomicilio.mx",
        "plataforma": "fad",
    },
}

# ─────────────────────────────────────────────
#  Tiempos (milisegundos)
# ─────────────────────────────────────────────
TIMEOUT_DEFAULT = 20_000
TIMEOUT_GUARDAR = 30_000     # espera a que se cierre el modal tras guardar
TIMEOUT_AUTOCOMPLETE = 10_000  # espera a sugerencias de Google / lat-long
DELAY_TECLEO = 35            # ms entre teclas al escribir la dirección

# ─────────────────────────────────────────────
#  Estados que se escriben en el Excel
# ─────────────────────────────────────────────
OK = "OK"
REVISAR = "REVISAR"
YA_EXISTE = "YA EXISTE"
ERROR = "ERROR"
DATOS_INVALIDOS = "DATOS INVALIDOS"
NO_ENCONTRADO = "NO ENCONTRADO"

# Filas con estos estados se saltan en una nueva corrida (no se re-suben).
ESTADOS_TERMINADOS = {OK, YA_EXISTE, REVISAR}

COLORES = {          # relleno de la fila en Excel
    OK: "C6EFCE",               # verde
    REVISAR: "FFEB9C",          # amarillo
    YA_EXISTE: "DDEBF7",        # azul claro
    ERROR: "FFC7CE",            # rojo
    DATOS_INVALIDOS: "FFC7CE",  # rojo
    NO_ENCONTRADO: "FFC7CE",    # rojo
}
