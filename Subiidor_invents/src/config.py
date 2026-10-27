"""
Configuración general y registro de marketplaces (MKP) del subidor de inventarios.

Para agregar un MKP: añade una entrada a MARKETPLACES y sus credenciales en .env
(MKP_<CLAVE>_URL / _USUARIO / _PASSWORD).
"""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
OUTPUT_DIR = RAIZ / "output"
BACKUP_DIR = OUTPUT_DIR / "backups"
LOGS_DIR = RAIZ / "logs"
INVENTARIOS_DIR = RAIZ / "Inventarios"

EXCEL_DEFAULT = RAIZ / "Enlaces por nombre.xlsx"

MARKETPLACES = {
    "FAD": {"nombre": "Farmacias a Domicilio", "url": "https://farmaciasadomicilio.mx", "plataforma": "fad"},
    "UNEFARM": {"nombre": "UNEFARM", "url": "https://unefarm.farmaciasadomicilio.mx", "plataforma": "fad"},
}

# Tras subir un CSV, el panel lo procesa en segundo plano. Se espera hasta este
# tiempo (segundos) a que el archivo pase a éxito/error; si sigue en proceso, la fila
# queda EN PROCESO y se confirma después con --verificar.
ESPERA_PROCESO = 90
INTERVALO_SONDEO = 5

# ─────────────────────────────────────────────
#  Estados que se escriben en el Excel
# ─────────────────────────────────────────────
OK = "OK"
EN_PROCESO = "EN PROCESO"          # subido; el panel aún lo está procesando
NO_ENCONTRADO = "NO ENCONTRADO"    # no hay proveedor con ese nombre EXACTO
ERROR = "ERROR"
DATOS_INVALIDOS = "DATOS INVALIDOS"  # fila o archivo CSV con problemas (no se sube)

# Filas con estos estados no se vuelven a subir (EN PROCESO se confirma con --verificar).
ESTADOS_TERMINADOS = {OK, EN_PROCESO}

COLORES = {
    OK: "C6EFCE",               # verde
    EN_PROCESO: "FFEB9C",       # amarillo
    NO_ENCONTRADO: "FFC7CE",    # rojo
    ERROR: "FFC7CE",            # rojo
    DATOS_INVALIDOS: "FFC7CE",  # rojo
}
