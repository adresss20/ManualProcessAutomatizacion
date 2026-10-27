"""
Alta automática de proveedores en marketplaces (MKP) desde Excel.

Uso (desde la carpeta del proyecto):
  py src\\main.py                      menú para elegir MKP y sube los pendientes
  py src\\main.py --mkp FAD            sin menú
  py src\\main.py --mkp FAD --diagnose revisa el formulario sin guardar nada
  py src\\main.py --mkp FAD --limit 3  prueba con pocos
  py src\\main.py --mkp FAD --filas 10-20
  py src\\main.py --mkp FAD --verificar   solo confirma que cada proveedor esté en el panel
  py src\\main.py --validar-excel      solo revisa los datos del Excel (no abre navegador)
"""
import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from config import (DATOS_INVALIDOS, ERROR, ESTADOS_TERMINADOS, EXCEL_DEFAULT, LOGS_DIR, MARKETPLACES,
                    NO_ENCONTRADO, OK, RAIZ, REVISAR, TIMEOUT_DEFAULT, YA_EXISTE)
from entorno import cargar_dotenv, credenciales, tiene_credenciales
from excel_io import LibroProveedores, norm

log = logging.getLogger("proveedores")


def configurar_log(mkp: str) -> Path:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    ruta = LOGS_DIR / f"subida_{mkp}_{datetime.now():%Y%m%d_%H%M%S}.log"
    fmt = logging.Formatter("%(asctime)s  %(message)s", "%H:%M:%S")
    for h in (logging.StreamHandler(sys.stdout), logging.FileHandler(ruta, encoding="utf-8")):
        h.setFormatter(fmt)
        log.addHandler(h)
    log.setLevel(logging.INFO)
    return ruta


def elegir_mkp(arg: str | None) -> str:
    if arg:
        clave = arg.upper()
        if clave not in MARKETPLACES:
            raise SystemExit(f"MKP '{arg}' no existe. Opciones: {', '.join(MARKETPLACES)}")
        return clave
    claves = list(MARKETPLACES)
    print("\n¿A qué marketplace quieres subir los proveedores?\n")
    for i, k in enumerate(claves, 1):
        cred = "credenciales en .env" if tiene_credenciales(k) else "pedirá usuario/contraseña"
        print(f"  {i}. {MARKETPLACES[k]['nombre']:<25} [{k}]  ({cred})")
    while True:
        r = input("\nNúmero o clave: ").strip().upper()
        if r.isdigit() and 1 <= int(r) <= len(claves):
            return claves[int(r) - 1]
        if r in MARKETPLACES:
            return r
        print("Opción no válida.")


def ruta_excel(arg: str | None) -> Path:
    if arg:
        return Path(arg).resolve()
    if EXCEL_DEFAULT.is_file():
        return EXCEL_DEFAULT
    xs = [p for p in RAIZ.glob("*.xlsx") if not p.name.startswith("~$")]
    if len(xs) == 1:
        return xs[0]
    raise SystemExit("No encuentro el Excel de proveedores; usa --excel <ruta>.")


def rango_filas(texto: str | None):
    if not texto:
        return None
    a, _, b = texto.partition("-")
    return int(a), int(b or a)


def main() -> None:
    ap = argparse.ArgumentParser(description="Alta automática de proveedores en MKP desde Excel")
    ap.add_argument("--mkp", help=f"Clave del marketplace: {', '.join(MARKETPLACES)}")
    ap.add_argument("--excel", help="Ruta del Excel (por defecto Información_Proveedores.xlsx)")
    ap.add_argument("--diagnose", action="store_true", help="Revisa el formulario sin guardar")
    ap.add_argument("--verificar", action="store_true", help="Solo verifica que estén en el panel")
    ap.add_argument("--validar-excel", action="store_true", help="Solo valida los datos del Excel")
    ap.add_argument("--limit", type=int, default=0, help="Máximo de proveedores a procesar")
    ap.add_argument("--filas", help="Rango de filas del Excel, ej. 10-20")
    ap.add_argument("--headless", action="store_true", help="Navegador oculto")
    args = ap.parse_args()

    cargar_dotenv()
    mkp = "EXCEL" if args.validar_excel and not args.mkp else elegir_mkp(args.mkp)
    ruta_log = configurar_log(mkp)
    excel = ruta_excel(args.excel)
    libro = LibroProveedores(excel, mkp)
    proveedores = libro.proveedores()
    rango = rango_filas(args.filas)
    if rango:
        proveedores = [p for p in proveedores if rango[0] <= p.fila <= rango[1]]
    log.info("Excel: %s — %d proveedores leídos", excel.name, len(proveedores))

    # ── 1. Validación de datos (sin navegador) ──
    invalidos = [p for p in proveedores if p.errores]
    for p in invalidos:
        log.info("  fila %d %-35s DATOS INVÁLIDOS: %s", p.fila, p.nombre, "; ".join(p.errores))
    if args.validar_excel:
        log.info("Válidos: %d · Inválidos: %d", len(proveedores) - len(invalidos), len(invalidos))
        return

    from playwright.sync_api import sync_playwright
    from plataformas import PLATAFORMAS, ErrorAlta

    url, usuario, password = credenciales(mkp)
    if not args.diagnose:
        log.info("Respaldo del Excel: %s", libro.respaldar().name)

    resumen: dict[str, int] = {}
    with sync_playwright() as pw:
        navegador = pw.chromium.launch(headless=args.headless, slow_mo=0 if args.headless else 50)
        contexto = navegador.new_context(locale="es-MX", viewport={"width": 1440, "height": 900})
        page = contexto.new_page()
        page.set_default_timeout(TIMEOUT_DEFAULT)
        plataforma = PLATAFORMAS[MARKETPLACES[mkp]["plataforma"]](page, url, log, LOGS_DIR / f"diag_{mkp}")
        plataforma.login(usuario, password)

        if args.diagnose:
            ejemplo = next((p for p in proveedores if not p.errores), None)
            if ejemplo is None:
                raise SystemExit("No hay ningún proveedor válido en el Excel para el diagnóstico.")
            plataforma.diagnosticar(ejemplo)
            navegador.close()
            return

        procesados = 0
        fallos_seguidos = 0
        try:
            for p in proveedores:
                if args.limit and procesados >= args.limit:
                    break
                if p.errores:
                    if not args.verificar:
                        _registrar(libro, p, DATOS_INVALIDOS, "; ".join(p.errores), resumen)
                    continue
                if not args.verificar:
                    previo = libro.estado(p.fila)
                    if previo in ESTADOS_TERMINADOS:
                        log.info("  fila %d %-35s ya marcado %s, se omite", p.fila, p.nombre, previo)
                        continue
                    log.info("▶ fila %d  %s", p.fila, p.nombre)
                procesados += 1

                # Un fallo inesperado (página lenta, elemento que no aparece…) se anota
                # como ERROR en esa fila y se sigue con la siguiente.
                try:
                    if args.verificar:
                        _verificar_fila(plataforma, libro, p, resumen)
                    else:
                        _alta_fila(plataforma, libro, p, resumen, ErrorAlta)
                    fallos_seguidos = 0
                except Exception as e:
                    fallos_seguidos += 1
                    plataforma._captura(f"fila{p.fila}_inesperado")
                    _registrar(libro, p, ERROR, f"Error inesperado: {str(e).splitlines()[0]}", resumen)
                    if fallos_seguidos >= 5:
                        log.info("5 errores inesperados seguidos: se detiene la corrida para revisar.")
                        break
        except KeyboardInterrupt:
            log.info("Interrumpido por el usuario. Lo procesado ya está guardado en el Excel.")
        finally:
            navegador.close()

    log.info("─" * 60)
    log.info("Resumen %s: %s", mkp, ", ".join(f"{k}: {v}" for k, v in resumen.items()) or "nada que procesar")
    log.info("Resultados en: %s", libro.destino)
    if libro.destino != libro.ruta:
        log.info("(El Excel original estaba abierto; ciérralo la próxima vez para escribir directo en él.)")
    log.info("Log: %s", ruta_log)


def _verificar_fila(plataforma, libro, p, resumen) -> None:
    encontrado = plataforma.buscar(p.nombre)
    if encontrado:
        estado, obs = _comparar(p, encontrado)
    else:
        estado, obs = NO_ENCONTRADO, "No aparece en el listado de proveedores del panel"
    _registrar(libro, p, estado, obs, resumen)


def _alta_fila(plataforma, libro, p, resumen, ErrorAlta) -> None:
    existente = plataforma.buscar(p.nombre)
    if existente:
        _registrar(libro, p, YA_EXISTE,
                   f"Ya estaba en el panel (pestaña {existente.pestana}); no se volvió a crear", resumen)
        return
    try:
        res = plataforma.alta(p)
    except ErrorAlta as e:
        _registrar(libro, p, ERROR, str(e), resumen)
        return

    # ── Validador post-guardado ──
    encontrado = plataforma.buscar(p.nombre)
    if not encontrado:
        _registrar(libro, p, ERROR, "Se envió el formulario pero no aparece en el listado", resumen)
        return
    estado, obs = _comparar(p, encontrado)
    avisos = res.advertencias + ([obs] if obs else [])
    _registrar(libro, p, REVISAR if avisos else estado, "; ".join(avisos), resumen)


def _comparar(p, encontrado) -> tuple[str, str]:
    """Confirma que el listado muestre la dirección esperada (por plus code)."""
    if p.plus_code and encontrado.direccion and p.plus_code not in encontrado.direccion.upper():
        return REVISAR, f"En el panel la dirección es '{encontrado.direccion}' (esperado {p.plus_code})"
    if encontrado.pestana and norm(encontrado.pestana) != "activo":
        return REVISAR, f"Quedó en la pestaña '{encontrado.pestana}'"
    return OK, ""


def _registrar(libro, p, estado: str, obs: str, resumen: dict) -> None:
    libro.marcar(p.fila, estado, obs)
    resumen[estado] = resumen.get(estado, 0) + 1
    log.info("  fila %d %-35s %s%s", p.fila, p.nombre, estado, f" — {obs}" if obs else "")


if __name__ == "__main__":
    main()
