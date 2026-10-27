"""
=============================================================
  Farmacia a Domicilio — Cargador masivo de marcas
=============================================================
Autor : Claude (Cowork)
Uso   :
    1. Descarga el Excel a tu computadora.
    2. Instala dependencias:
           pip install requests openpyxl beautifulsoup4 rapidfuzz
    3. Configura CREDENCIALES y RUTAS en la sección CONFIG.
    4. Ejecuta:
           python agregar_marcas.py

El script:
  - Lee el Excel de fabricantes/marcas
  - Omite las filas cuya celda de "Fabricante" ya tiene fondo verde
  - Agrega cada marca al sitio vía POST a /client/brand
  - Mapea los nombres de categorías del Excel a los IDs del sitio
    (usando coincidencia exacta y, si no encuentra, fuzzy matching)
  - Pinta la fila de verde en el Excel cuando la marca se agrega con éxito
  - Guarda el Excel después de cada marca (así si el proceso se interrumpe
    no pierdes progreso)
=============================================================
"""

import sys
import time
import logging
from pathlib import Path

import requests
from bs4 import BeautifulSoup
import openpyxl
from openpyxl.styles import PatternFill
from rapidfuzz import process as fuzz_process, fuzz

# ─────────────────────────────────────────────
#  CONFIG  ← ajusta estos valores
# ─────────────────────────────────────────────
BASE_URL      = "https://farmaciasadomicilio.mx"
LOGIN_URL     = f"{BASE_URL}/client/login"
CATEGORY_URL  = f"{BASE_URL}/client/category"
BRAND_URL     = f"{BASE_URL}/client/brand"

# Credenciales del panel de Farmacia a Domicilio
EMAIL    = "TU_EMAIL@ejemplo.com"
PASSWORD = "TU_CONTRASEÑA"

# Ruta al archivo Excel en tu computadora
EXCEL_PATH = r"C:\Users\TuUsuario\Downloads\fabricantes.xlsx"

# ── Columnas del Excel (índice base-1) ────────
COL_FABRICANTE = 1   # Columna A: nombre de la marca (Fabricante)
# Columnas de categorías: ajusta según tu Excel.
# Cada columna con "X" o cualquier valor indica que la marca pertenece a esa categoría.
# Si tus categorías están en una sola celda separadas por comas, cambia CATEGORY_MODE a "single_cell"
# Si cada categoría ocupa una columna diferente, usa "multi_column"
CATEGORY_MODE = "multi_column"  # "multi_column" | "single_cell"

# Para CATEGORY_MODE = "multi_column":
#   Dict  {índice_columna: "Nombre de categoría en el sitio"}
CATEGORY_COLUMNS = {
    # Ejemplo — ajusta los índices y nombres según tu Excel real:
    # 3:  "Cuidado personal y belleza",
    # 4:  "Dermocosméticos",
    # 5:  "Bebés",
    # 6:  "Medicamentos",
    # 7:  "Alimentos y bebidas",
    # 8:  "Equipo y botiquín",
}

# Para CATEGORY_MODE = "single_cell":
COL_CATEGORIES = 2    # columna que contiene categorías separadas por comas
CATEGORY_SEP   = ","  # separador entre categorías en esa celda

# Fila donde empieza la data (si hay encabezados en fila 1, empieza en 2)
DATA_START_ROW = 2

# Idioma: 148 = Español, 1 = Inglés (mismos IDs detectados en el sitio)
LANG_SPANISH = "148"
LANG_ENGLISH = "1"

# Segundos de espera entre peticiones (para no saturar el servidor)
DELAY_BETWEEN = 1.0

# Score mínimo de similitud para aceptar fuzzy match (0-100)
FUZZY_MIN_SCORE = 70
# ─────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("agregar_marcas.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

GREEN_FILL = PatternFill(start_color="92D050", end_color="92D050", fill_type="solid")


# ══════════════════════════════════════════════
#  Sesión y autenticación
# ══════════════════════════════════════════════

def crear_sesion() -> requests.Session:
    """Crea sesión HTTP con headers de navegador."""
    s = requests.Session()
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/127.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
    })
    return s


def iniciar_sesion(session: requests.Session) -> None:
    """Hace login en el panel de Farmacia a Domicilio."""
    # 1. GET a la página de login para obtener CSRF token
    r = session.get(LOGIN_URL, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    token_tag = soup.find("input", {"name": "_token"})
    if not token_tag:
        raise RuntimeError("No se encontró el _token en la página de login.")
    token = token_tag["value"]

    # 2. POST con credenciales
    payload = {
        "_token": token,
        "email": EMAIL,
        "password": PASSWORD,
    }
    r2 = session.post(LOGIN_URL, data=payload, timeout=30, allow_redirects=True)
    r2.raise_for_status()

    # Verificar que estamos logueados (la página de login redirige al dashboard)
    if "login" in r2.url.lower() or "password" in r2.text.lower()[:500]:
        raise RuntimeError(
            "Login fallido. Verifica EMAIL y PASSWORD en la sección CONFIG."
        )
    log.info("✔ Login exitoso.")


# ══════════════════════════════════════════════
#  Categorías
# ══════════════════════════════════════════════

def obtener_csrf_y_categorias(session: requests.Session) -> tuple[str, dict[str, str]]:
    """
    Devuelve (csrf_token, {nombre_limpio: id}) desde la página /client/category.
    """
    r = session.get(CATEGORY_URL, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # CSRF token
    token_tag = soup.find("input", {"name": "_token"})
    if not token_tag:
        raise RuntimeError("No se encontró _token en la página de categorías.")
    csrf = token_tag["value"]

    # Categorías del <select id="cateSelectBox">
    select = soup.find("select", {"id": "cateSelectBox"})
    cats: dict[str, str] = {}
    if select:
        for opt in select.find_all("option"):
            val = opt.get("value", "").strip()
            txt = opt.get_text(strip=True).lstrip("> ").strip()
            if val and txt:
                cats[txt.lower()] = val
    else:
        log.warning("No se encontró #cateSelectBox. Verifica que estés logueado.")

    log.info(f"✔ {len(cats)} categorías cargadas del sitio.")
    return csrf, cats


def resolver_categorias(
    nombres_raw: list[str],
    cats_sitio: dict[str, str],   # {nombre_lower: id}
) -> list[str]:
    """
    Mapea nombres de categorías del Excel a IDs del sitio.
    Intenta coincidencia exacta primero, luego fuzzy.
    """
    ids_encontrados: list[str] = []
    sitio_keys = list(cats_sitio.keys())

    for nombre in nombres_raw:
        nombre = nombre.strip()
        if not nombre:
            continue
        nombre_lower = nombre.lower()

        # Coincidencia exacta
        if nombre_lower in cats_sitio:
            ids_encontrados.append(cats_sitio[nombre_lower])
            continue

        # Fuzzy matching
        resultado = fuzz_process.extractOne(
            nombre_lower, sitio_keys, scorer=fuzz.token_sort_ratio
        )
        if resultado and resultado[1] >= FUZZY_MIN_SCORE:
            matched_key = resultado[0]
            log.debug(
                f"  Fuzzy: '{nombre}' → '{matched_key}' "
                f"(score {resultado[1]})"
            )
            ids_encontrados.append(cats_sitio[matched_key])
        else:
            log.warning(
                f"  ⚠ No se encontró categoría para: '{nombre}' "
                f"(mejor coincidencia: {resultado})"
            )

    return list(dict.fromkeys(ids_encontrados))  # deduplicar sin perder orden


# ══════════════════════════════════════════════
#  Agregar una marca al sitio
# ══════════════════════════════════════════════

def agregar_marca(
    session: requests.Session,
    csrf: str,
    nombre_es: str,
    nombre_en: str,
    cat_ids: list[str],
) -> bool:
    """
    POST /client/brand con los datos de la marca.
    Devuelve True si el servidor respondió con 200/302 (éxito).
    """
    # Laravel espera listas como pares campo[]=valor repetidos
    data: list[tuple[str, str]] = [
        ("_token", csrf),
        ("language_id[]", LANG_SPANISH),
        ("title[]", nombre_es),
        ("language_id[]", LANG_ENGLISH),
        ("title[]", nombre_en),
    ]
    for cid in cat_ids:
        data.append(("cate_id[]", cid))

    try:
        r = session.post(
            BRAND_URL,
            data=data,
            timeout=30,
            allow_redirects=True,
        )
        # El sitio redirige a /client/category tras éxito
        if r.status_code in (200, 302) and "category" in r.url:
            return True
        # También verificamos que no haya mensaje de error en la respuesta
        if "error" in r.text.lower()[:1000] or r.status_code >= 400:
            log.error(f"  Respuesta inesperada ({r.status_code}): {r.url}")
            return False
        return True
    except requests.RequestException as e:
        log.error(f"  Error de red al agregar '{nombre_es}': {e}")
        return False


# ══════════════════════════════════════════════
#  Leer categorías desde una fila del Excel
# ══════════════════════════════════════════════

def categorias_de_fila(row) -> list[str]:
    """
    Extrae los nombres de categorías de una fila del Excel
    según CATEGORY_MODE configurado.
    """
    if CATEGORY_MODE == "multi_column":
        nombres = []
        for col_idx, cat_name in CATEGORY_COLUMNS.items():
            cell = row[col_idx - 1]  # openpyxl usa índice 0
            val = cell.value
            # Si la celda tiene contenido (X, 1, True, "si", etc.) → pertenece
            if val is not None and str(val).strip().upper() not in ("", "0", "NO", "FALSE", "N"):
                nombres.append(cat_name)
        return nombres

    else:  # single_cell
        cell = row[COL_CATEGORIES - 1]
        raw = str(cell.value or "")
        return [c.strip() for c in raw.split(CATEGORY_SEP) if c.strip()]


def es_fila_verde(row) -> bool:
    """Devuelve True si la celda de Fabricante ya tiene fondo verde."""
    fill = row[COL_FABRICANTE - 1].fill
    if fill and fill.fill_type not in (None, "none"):
        color = fill.fgColor
        if color:
            rgb = color.rgb if hasattr(color, "rgb") else ""
            # Acepta cualquier tono de verde (92D050, 00FF00, etc.)
            if rgb and rgb[1:3].upper() in ("92", "70", "00") or rgb.upper() in (
                "FF92D050", "FF00FF00", "FF70AD47"
            ):
                return True
    return False


def pintar_verde(row, wb: openpyxl.Workbook, excel_path: str) -> None:
    """Pinta todas las celdas de la fila de verde y guarda el archivo."""
    for cell in row:
        cell.fill = GREEN_FILL
    wb.save(excel_path)


# ══════════════════════════════════════════════
#  Main
# ══════════════════════════════════════════════

def main():
    excel_path = Path(EXCEL_PATH)
    if not excel_path.exists():
        log.error(f"No se encontró el archivo Excel: {excel_path}")
        sys.exit(1)

    # ── Sesión HTTP ──────────────────────────
    session = crear_sesion()
    log.info("Iniciando sesión en Farmacia a Domicilio…")
    iniciar_sesion(session)

    # ── Categorías del sitio ─────────────────
    log.info("Obteniendo categorías del sitio…")
    csrf, cats_sitio = obtener_csrf_y_categorias(session)

    # ── Abrir Excel ──────────────────────────
    log.info(f"Abriendo Excel: {excel_path}")
    wb = openpyxl.load_workbook(str(excel_path))
    ws = wb.active

    total_rows    = ws.max_row - DATA_START_ROW + 1
    procesadas    = 0
    omitidas      = 0
    errores       = 0
    ya_verdes     = 0

    log.info(f"Total de filas de datos: {total_rows}")
    log.info("─" * 60)

    for row_idx, row in enumerate(
        ws.iter_rows(min_row=DATA_START_ROW), start=DATA_START_ROW
    ):
        # Nombre del fabricante
        nombre_cell = row[COL_FABRICANTE - 1]
        nombre = str(nombre_cell.value or "").strip()
        if not nombre:
            continue

        # ¿Ya está en verde? → saltar
        if es_fila_verde(row):
            ya_verdes += 1
            log.debug(f"  Fila {row_idx}: '{nombre}' ya está en verde, omitiendo.")
            continue

        log.info(f"Fila {row_idx}: Procesando '{nombre}'…")

        # Categorías de esta fila
        cat_nombres = categorias_de_fila(row)
        cat_ids     = resolver_categorias(cat_nombres, cats_sitio)

        if not cat_ids:
            log.warning(f"  ⚠ Sin categorías para '{nombre}'. Se agregará sin categoría.")

        # Refrescar CSRF cada 50 marcas (por si expira)
        if procesadas > 0 and procesadas % 50 == 0:
            log.info("  Refrescando token CSRF…")
            csrf, _ = obtener_csrf_y_categorias(session)

        # Agregar al sitio
        ok = agregar_marca(
            session,
            csrf,
            nombre_es=nombre,
            nombre_en=nombre,   # misma marca en inglés; ajusta si tienes columna separada
            cat_ids=cat_ids,
        )

        if ok:
            procesadas += 1
            pintar_verde(row, wb, str(excel_path))
            log.info(f"  ✔ '{nombre}' agregada (categorías: {cat_nombres})")
        else:
            errores += 1
            log.error(f"  ✘ Falló al agregar '{nombre}'")

        time.sleep(DELAY_BETWEEN)

    log.info("─" * 60)
    log.info(
        f"Proceso terminado.\n"
        f"  ✔ Agregadas exitosamente : {procesadas}\n"
        f"  ○ Ya estaban en verde    : {ya_verdes}\n"
        f"  ✘ Errores                : {errores}"
    )


if __name__ == "__main__":
    main()
