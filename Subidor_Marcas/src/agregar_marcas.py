"""
=============================================================
  Farmacia a Domicilio — Cargador masivo de marcas  (v2)
=============================================================
Sube en lote las marcas del Excel al panel de farmaciasadomicilio.mx,
asociando cada marca a sus categorías y marcando en verde en el Excel
las que se van creando con éxito.

Uso rápido
----------
  1. pip install -r requirements.txt
  2. Define tus credenciales del panel (NO se escriben en el código):
        Windows PowerShell:
            $env:FAD_EMAIL="tu_correo@dominio.com"
            $env:FAD_PASSWORD="tu_contraseña"
        (o crea src/config.local.py con FAD_EMAIL / FAD_PASSWORD)
  3. Prueba primero con pocas filas:
            python agregar_marcas.py --limit 5 --dry-run     # no envía nada, solo muestra el mapeo
            python agregar_marcas.py --limit 5                # crea 5 de verdad
  4. Corrida completa:
            python agregar_marcas.py

Qué hace
--------
  - Lee input/Marcas por crear.xlsx  (col B = marca, col C = categorías separadas por comas)
  - Omite las filas ya marcadas en verde (progreso resumible)
  - Descarga del sitio la lista de marcas YA existentes y también las omite (evita duplicados)
  - Mapea los nombres de categoría del Excel a los IDs reales del sitio
    (normalización de acentos/mayúsculas + alias para typos + fuzzy como último recurso)
  - POST /client/brand por cada marca; valida el éxito de verdad (redirect + sin errores)
  - Pinta la fila de verde y guarda el Excel tras cada éxito
  - Log detallado en logs/agregar_marcas.log
=============================================================
"""

import os
import re
import sys
import time
import argparse
import logging
import unicodedata
from pathlib import Path

import requests
from bs4 import BeautifulSoup
import openpyxl
from openpyxl.styles import PatternFill

try:
    from rapidfuzz import process as fuzz_process, fuzz
    HAVE_FUZZY = True
except ImportError:
    HAVE_FUZZY = False

# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────
BASE_URL         = "https://farmaciasadomicilio.mx"
LOGIN_URL        = f"{BASE_URL}/user/login"             # página con el formulario (GET)
LOGIN_POST_URL   = f"{BASE_URL}/user/loginViaUsername"  # endpoint AJAX real (POST) de autenticación
CATEGORY_URL     = f"{BASE_URL}/client/category"        # token CSRF + tabla de marcas existentes
BRAND_CREATE_URL = f"{BASE_URL}/client/brand/create"    # JSON con el <select> de las 474 categorías
BRAND_URL        = f"{BASE_URL}/client/brand"           # POST (multipart) para crear la marca

ROOT       = Path(__file__).resolve().parent.parent
EXCEL_PATH = ROOT / "input" / "Marcas por crear.xlsx"
LOG_PATH   = ROOT / "logs" / "agregar_marcas.log"

# Credenciales: se leen de variables de entorno o de src/config_local.py (no versionar).
EMAIL    = os.environ.get("FAD_EMAIL", "")
PASSWORD = os.environ.get("FAD_PASSWORD", "")
# Alternativa al login automático: cookie de una sesión ya abierta en el navegador
# (útil si el sitio pide OTP). Formato: "nombre=valor; nombre2=valor2"
COOKIE   = os.environ.get("FAD_COOKIE", "")
try:
    import config_local as _cl                                     # src/config_local.py
    EMAIL    = EMAIL    or getattr(_cl, "FAD_EMAIL", "")
    PASSWORD = PASSWORD or getattr(_cl, "FAD_PASSWORD", "")
    COOKIE   = COOKIE   or getattr(_cl, "FAD_COOKIE", "")
except Exception:
    pass

# Estructura del Excel (índice base-1)
COL_TOP        = 1   # A: ranking (no se usa para nada crítico)
COL_BRAND      = 2   # B: nombre de la marca / fabricante
COL_CATEGORIES = 3   # C: categorías separadas por comas
CATEGORY_SEP   = ","
DATA_START_ROW = 2   # fila 1 = encabezados

# Idiomas detectados en el sitio
LANG_SPANISH = "148"
LANG_ENGLISH = "1"

# Verde usado en el Excel para "ya creada" (mismo tono que Unilever/P&G ya marcadas)
GREEN_HEX  = "FFB5E6A2"
GREEN_FILL = PatternFill(start_color=GREEN_HEX, end_color=GREEN_HEX, fill_type="solid")

DELAY_BETWEEN   = 1.0    # segundos entre peticiones
FUZZY_MIN_SCORE = 82     # umbral alto: preferimos no mapear a arriesgar categoría equivocada

# Alias: nombre_normalizado_del_excel -> nombre_normalizado_del_sitio (para typos/variantes).
# La normalización quita acentos y pasa a minúsculas, así que aquí van en esa forma.
# Se completará contra la lista real del sitio; los que no resuelvan se registran en el log.
# Nombres del Excel que NO coinciden 1:1 con una categoría del sitio.
# El sitio no tiene "Súper"; se mapea al cajón más cercano (Abarrotes y limpieza).
# El resto del Excel coincide directo tras normalizar acentos/mayúsculas/espacios.
CATEGORY_ALIASES = {
    "super":                        "abarrotes y limpieza",
    "super y abarrotes":            "abarrotes y limpieza",
    "abarrotes":                    "abarrotes y limpieza",
    "limpieza y cuidado del hogar": "abarrotes y limpieza",
    # "protector solar" coincide exacto con la subcategoría del sitio (id 145).
}
# ─────────────────────────────────────────────

LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
# La consola de Windows suele ser cp1252 y truena con acentos/símbolos → forzamos utf-8.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
_console = logging.StreamHandler(sys.stdout)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    handlers=[
        _console,
        logging.FileHandler(str(LOG_PATH), encoding="utf-8"),
    ],
)
log = logging.getLogger("marcas")


def norm(s: str) -> str:
    """minúsculas, sin acentos, sin '>' de subcategoría, espacios colapsados."""
    s = (s or "").strip().lstrip(">").strip()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"\s+", " ", s).lower()
    return s


# ══════════════════════════════════════════════
#  Sesión / login
# ══════════════════════════════════════════════
def crear_sesion() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/127.0.0.0 Safari/537.36"),
        "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
    })
    return s


def _token_de(html: str) -> str:
    tag = BeautifulSoup(html, "html.parser").find("input", {"name": "_token"})
    return tag["value"] if tag and tag.has_attr("value") else ""


def iniciar_sesion(session: requests.Session) -> None:
    if not EMAIL or not PASSWORD:
        raise SystemExit(
            "Faltan credenciales. Define FAD_EMAIL / FAD_PASSWORD como variables de entorno "
            "o crea src/config_local.py con FAD_EMAIL y FAD_PASSWORD."
        )
    # 1) GET al login para tomar el formulario real (#login-form-new) y sus campos ocultos.
    r = session.get(LOGIN_URL, timeout=30); r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    form = next((f for f in soup.find_all("form")
                 if f.find("input", {"name": "password"})), None)
    if form is None:
        raise RuntimeError("No se encontró el formulario de login en /user/login.")

    # Replicamos lo que hace el JS: serializar el form (arrastra _token, device_type=web,
    # device_token=web, dialCode, countryData, …) y encima poner usuario/contraseña.
    payload = {}
    for inp in form.find_all("input"):
        name = inp.get("name")
        if name:
            payload[name] = inp.get("value", "") or ""
    payload["username"] = EMAIL          # el campo 'username' acepta el correo
    payload["password"] = PASSWORD
    token = payload.get("_token", "")
    if not token:
        raise RuntimeError("No se encontró _token en la página de login.")

    # 2) POST AJAX al endpoint real (/user/loginViaUsername). Devuelve JSON.
    headers = {
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRF-TOKEN": token,
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": LOGIN_URL,
        "Origin": BASE_URL,
    }
    r2 = session.post(LOGIN_POST_URL, data=payload, headers=headers,
                      timeout=30, allow_redirects=True)
    try:
        j = r2.json()
    except ValueError:
        raise RuntimeError(f"Respuesta no-JSON del login ({r2.status_code}). "
                           "¿Cambió el sitio? Usa el método por cookie (README).")

    data = j.get("data") or {}
    if j.get("status") == "Success" and str(data.get("is_email")) == "1":
        log.info("Login exitoso (%s).", EMAIL)
        # el redirect final asienta la sesión del panel
        session.get(data.get("redirect_to") or CATEGORY_URL, timeout=30)
        return
    if str(data.get("is_phone")) == "1":
        raise RuntimeError(
            "El sitio pidió verificación por OTP (teléfono). El login automático no puede pasarlo.\n"
            "  → Usa el método por cookie: set FAD_COOKIE=laravel_session=... (ver README)."
        )
    # cualquier otro caso = credenciales inválidas / usuario no existe
    raise RuntimeError(f"Login fallido: {j.get('message', j)}")


def cargar_cookie(session: requests.Session) -> None:
    """Inyecta la cookie de sesión copiada del navegador (fallback anti-OTP)."""
    for parte in COOKIE.split(";"):
        parte = parte.strip()
        if "=" in parte:
            k, v = parte.split("=", 1)
            session.cookies.set(k.strip(), v.strip(), domain="farmaciasadomicilio.mx")
    if not sesion_viva(session):
        raise RuntimeError(
            "La cookie FAD_COOKIE no da una sesión válida (¿expiró o está incompleta?). "
            "Vuelve a copiarla del navegador ya logueado."
        )
    log.info("Sesión por cookie válida.")


def sesion_viva(session: requests.Session) -> bool:
    try:
        r = session.get(CATEGORY_URL, timeout=20, allow_redirects=False)
        return r.status_code == 200 and "login" not in r.headers.get("Location", "")
    except requests.RequestException:
        return False


# ══════════════════════════════════════════════
#  Categorías y marcas existentes del sitio
# ══════════════════════════════════════════════
def obtener_csrf_y_categorias(session: requests.Session):
    """
    Devuelve (csrf, {nombre_norm: id}).
    - CSRF: del formulario #addBrandForm en /client/category.
    - Categorías: del JSON de /client/brand/create → html → <select id=cateSelectBox>.
    """
    r = session.get(CATEGORY_URL, timeout=30); r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    form = soup.find("form", {"id": "addBrandForm"})
    tok = form.find("input", {"name": "_token"}) if form else None
    csrf = tok["value"] if tok and tok.has_attr("value") else _token_de(r.text)
    if not csrf:
        raise RuntimeError("No se encontró _token en /client/category (¿sesión caída?).")

    rc = session.get(BRAND_CREATE_URL, timeout=30,
                     headers={"X-Requested-With": "XMLHttpRequest"})
    rc.raise_for_status()
    try:
        html = rc.json().get("html", "")
    except ValueError:
        html = rc.text                       # por si algún día lo sirven sin envolver
    csoup = BeautifulSoup(html, "html.parser")
    select = csoup.find("select", {"id": "cateSelectBox"})
    cats = {}
    if select:
        for opt in select.find_all("option"):
            val = (opt.get("value") or "").strip()
            key = norm(opt.get_text())       # norm() ya quita el ">" de subcategoría
            if val and key:
                cats[key] = val
    if not cats:
        raise RuntimeError("No se pudieron leer categorías de /client/brand/create.")
    log.info("%d categorías cargadas del sitio.", len(cats))
    return csrf, cats


def obtener_marcas_existentes(session: requests.Session) -> set:
    """Nombres (normalizados) de marcas ya en el sitio (tabla #brand-datatable)."""
    existentes = set()
    try:
        r = session.get(CATEGORY_URL, timeout=30)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            tbl = soup.find("table", {"id": "brand-datatable"})
            body = tbl.find("tbody") if tbl else None
            for tr in (body.find_all("tr") if body else []):
                tds = tr.find_all("td")
                # 3ª celda = nombre de la marca
                if len(tds) >= 3:
                    nombre = tds[2].get_text(strip=True)
                    if nombre:
                        existentes.add(norm(nombre))
    except requests.RequestException as e:
        log.warning("No se pudo leer la lista de marcas existentes: %s", e)
    log.info("%d marcas existentes leídas del sitio (para evitar duplicados).", len(existentes))
    return existentes


# ══════════════════════════════════════════════
#  Resolución de categorías Excel -> IDs
# ══════════════════════════════════════════════
def resolver_categorias(nombres_raw, cats_sitio, sin_match: set):
    ids, keys = [], list(cats_sitio.keys())
    for nombre in nombres_raw:
        n = norm(nombre)
        if not n:
            continue
        n = CATEGORY_ALIASES.get(n, n)     # aplica alias si existe
        if n in cats_sitio:                 # exacto (normalizado)
            ids.append(cats_sitio[n]); continue
        if HAVE_FUZZY and keys:
            m = fuzz_process.extractOne(n, keys, scorer=fuzz.token_sort_ratio)
            if m and m[1] >= FUZZY_MIN_SCORE:
                log.info("  fuzzy: '%s' -> '%s' (%.0f)", nombre, m[0], m[1])
                ids.append(cats_sitio[m[0]]); continue
        sin_match.add(nombre.strip())
        log.warning("  SIN categoría en el sitio: '%s'", nombre.strip())
    return list(dict.fromkeys(ids))         # dedup preservando orden


# ══════════════════════════════════════════════
#  Alta de una marca
# ══════════════════════════════════════════════
def agregar_marca(session, csrf, nombre, cat_ids):
    data = [("_token", csrf),
            ("language_id[]", LANG_SPANISH), ("title[]", nombre),
            ("language_id[]", LANG_ENGLISH), ("title[]", nombre)]
    for cid in cat_ids:
        data.append(("cate_id[]", cid))
    try:
        r = session.post(BRAND_URL, data=data, timeout=30, allow_redirects=True)
    except requests.RequestException as e:
        log.error("  red al agregar '%s': %s", nombre, e)
        return False
    # El form hace un POST normal y Laravel redirige a /client/category al guardar.
    if r.status_code in (200, 302) and "/client/category" in r.url:
        return True
    # Por si algún día responden JSON:
    try:
        j = r.json()
        if j.get("success") or str(j.get("status", "")).lower() == "success":
            return True
    except ValueError:
        pass
    log.error("  respuesta inesperada para '%s': %s %s", nombre, r.status_code, r.url)
    return False


# ══════════════════════════════════════════════
#  Excel helpers
# ══════════════════════════════════════════════
def celda_verde(cell) -> bool:
    """True si la celda tiene CUALQUIER relleno sólido (en este Excel = ya creada)."""
    f = cell.fill
    return bool(f and f.fill_type and f.fill_type != "none")


def pintar_fila(ws, row_idx, wb):
    for col in range(1, ws.max_column + 1):
        ws.cell(row_idx, col).fill = GREEN_FILL
    wb.save(str(EXCEL_PATH))


# ══════════════════════════════════════════════
#  Diagnóstico: volcar estructura real del panel
# ══════════════════════════════════════════════
def diagnosticar(session: requests.Session) -> None:
    """Ya logueado, guarda el HTML de las páginas del panel e imprime dónde están
    los <select>/<form> y cualquier cosa relacionada con 'cate'/'brand'."""
    logs_dir = LOG_PATH.parent
    urls = [
        f"{BASE_URL}/client/category",
        f"{BASE_URL}/client/brand",
        f"{BASE_URL}/client/brand/create",
        f"{BASE_URL}/client/brands",
    ]
    for url in urls:
        try:
            r = session.get(url, timeout=30, allow_redirects=True)
        except requests.RequestException as e:
            log.warning("GET %s -> error %s", url, e); continue
        slug = re.sub(r"[^a-z]+", "_", url.split("/client/")[-1].lower()) or "root"
        out = logs_dir / f"diag_{slug}.html"
        out.write_text(r.text, encoding="utf-8")
        log.info("GET %s -> %s (%d bytes, final=%s) guardado en %s",
                 url, r.status_code, len(r.text), r.url, out.name)
        if r.status_code != 200 or "login" in r.url.lower():
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        selects = soup.find_all("select")
        log.info("  <select> encontrados: %d", len(selects))
        for s in selects:
            log.info("    select id=%r name=%r  #options=%d",
                     s.get("id"), s.get("name"), len(s.find_all("option")))
        # elementos con 'cate' o 'brand' en id/name
        for el in soup.find_all(attrs={"id": re.compile("cate|brand", re.I)}):
            log.info("    id~cate/brand: <%s id=%r name=%r>", el.name, el.get("id"), el.get("name"))
        for el in soup.find_all(attrs={"name": re.compile("cate|brand|title|language", re.I)}):
            log.info("    name~: <%s name=%r>", el.name, el.get("name"))
        # posibles endpoints en el JS de la página (rutas que contengan brand/category)
        for m in set(re.findall(r'https://farmaciasadomicilio\.mx/[A-Za-z0-9_/\-]*(?:brand|categor|cate)[A-Za-z0-9_/\-]*', r.text)):
            log.info("    url en página: %s", m)
    log.info("Diagnóstico terminado. Revisa los archivos logs/diag_*.html y pásame lo que veas.")


# ══════════════════════════════════════════════
#  Main
# ══════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="procesar solo N marcas (0 = todas)")
    ap.add_argument("--dry-run", action="store_true", help="no envía nada; solo muestra el mapeo")
    ap.add_argument("--diagnose", action="store_true",
                    help="loguea y vuelca el HTML de las páginas del panel para inspeccionar su estructura real")
    args = ap.parse_args()

    if args.diagnose:
        session = crear_sesion()
        if COOKIE:
            cargar_cookie(session)
        else:
            iniciar_sesion(session)
        diagnosticar(session)
        return

    if not EXCEL_PATH.exists():
        log.error("No existe el Excel: %s", EXCEL_PATH); sys.exit(1)

    session = crear_sesion()
    cats_sitio, existentes, csrf = {}, set(), ""
    if not args.dry_run:
        if COOKIE:
            log.info("Usando sesión por cookie (FAD_COOKIE)…")
            cargar_cookie(session)
        else:
            log.info("Iniciando sesión…")
            iniciar_sesion(session)
        csrf, cats_sitio = obtener_csrf_y_categorias(session)
        existentes = obtener_marcas_existentes(session)
    else:
        log.info("DRY-RUN: no hay login; el mapeo de categorías no se validará contra el sitio.")

    wb = openpyxl.load_workbook(str(EXCEL_PATH))
    ws = wb.active

    hechas = saltadas_verde = saltadas_dup = errores = vistas = 0
    sin_match = set()

    for row_idx in range(DATA_START_ROW, ws.max_row + 1):
        nombre = str(ws.cell(row_idx, COL_BRAND).value or "").strip()
        if not nombre:
            continue
        if celda_verde(ws.cell(row_idx, COL_BRAND)):
            saltadas_verde += 1
            continue
        if norm(nombre) in existentes:
            log.info("Fila %d: '%s' ya existe en el sitio → marco verde y sigo.", row_idx, nombre)
            if not args.dry_run:
                pintar_fila(ws, row_idx, wb)
            saltadas_dup += 1
            continue

        cat_raw = str(ws.cell(row_idx, COL_CATEGORIES).value or "")
        cat_nombres = [c.strip() for c in cat_raw.split(CATEGORY_SEP) if c.strip()]
        cat_ids = resolver_categorias(cat_nombres, cats_sitio, sin_match) if not args.dry_run else []

        vistas += 1
        if args.dry_run:
            log.info("Fila %d: '%s'  cats=%s", row_idx, nombre, cat_nombres)
        else:
            if not cat_ids:
                log.warning("Fila %d: '%s' SIN categorías mapeadas — se OMITE (revísala manual).",
                            row_idx, nombre)
                errores += 1
                continue
            if hechas and hechas % 50 == 0:          # refrescar CSRF/sesión periódicamente
                if not sesion_viva(session):
                    log.info("Sesión caída, re-login…"); iniciar_sesion(session)
                csrf, cats_sitio = obtener_csrf_y_categorias(session)

            if agregar_marca(session, csrf, nombre, cat_ids):
                hechas += 1
                pintar_fila(ws, row_idx, wb)
                log.info("Fila %d: OK '%s' (%d cats)", row_idx, nombre, len(cat_ids))
            else:
                errores += 1
                log.error("Fila %d: FAIL '%s'", row_idx, nombre)
            time.sleep(DELAY_BETWEEN)

        if args.limit and vistas >= args.limit:
            log.info("Límite de %d alcanzado, deteniendo.", args.limit)
            break

    log.info("-" * 60)
    log.info("FIN.  creadas=%d  ya_verdes=%d  ya_en_sitio=%d  errores/sin_cat=%d",
             hechas, saltadas_verde, saltadas_dup, errores)
    if sin_match:
        log.warning("Categorías del Excel que NO se pudieron mapear (%d): %s",
                    len(sin_match), ", ".join(sorted(sin_match)))


if __name__ == "__main__":
    main()
