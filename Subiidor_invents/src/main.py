"""
Subidor de inventarios: importa el CSV de inventario de cada proveedor en el MKP,
según "Enlaces por nombre.xlsx" (Nombre_proveedor → Name_inventario).

Uso (desde la carpeta del proyecto):
  py src\\main.py                        menú para elegir MKP y subir los pendientes
  py src\\main.py --mkp FAD              sin menú
  py src\\main.py --validar              solo revisa Excel + CSV (sin conectarse)
  py src\\main.py --convertir Inventario_tiendas.xlsx
                                         regenera el CSV desde el .xlsx con los SKU completos
  py src\\main.py --mkp FAD --diagnose   revisa el formulario de importación sin subir nada
  py src\\main.py --mkp FAD --limit 2    prueba con pocos
  py src\\main.py --mkp FAD --verificar  confirma las filas EN PROCESO
"""
import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from config import (DATOS_INVALIDOS, EN_PROCESO, ERROR, ESPERA_PROCESO, ESTADOS_TERMINADOS, EXCEL_DEFAULT,
                    INTERVALO_SONDEO, INVENTARIOS_DIR, LOGS_DIR, MARKETPLACES, NO_ENCONTRADO, OK, RAIZ)
from entorno import cargar_dotenv, credenciales, tiene_credenciales
from excel_io import LibroEnlaces, norm
from inventario import convertir_xlsx, resolver_archivo, validar_csv

log = logging.getLogger("inventarios")


def configurar_log(etiqueta: str) -> Path:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    ruta = LOGS_DIR / f"inventarios_{etiqueta}_{datetime.now():%Y%m%d_%H%M%S}.log"
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
    print("\n¿A qué marketplace quieres subir los inventarios?\n")
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


class Archivos:
    """Resuelve y valida cada CSV una sola vez (el mismo archivo suele repetirse)."""

    def __init__(self, forzar: bool):
        self.forzar = forzar
        self.cache = {}

    def revisar(self, nombre: str):
        """-> (ruta | None, errores[], avisos[])"""
        if nombre not in self.cache:
            ruta, nota = resolver_archivo(nombre)
            if ruta is None:
                self.cache[nombre] = (None, [nota], [])
            else:
                v = validar_csv(ruta)
                avisos = ([nota] if nota else []) + v.avisos
                errores = list(v.errores)
                if errores and self.forzar:
                    avisos += [f"(--forzar) {e}" for e in errores]
                    errores = []
                self.cache[nombre] = (ruta, errores, avisos)
                log.info("Archivo '%s' → %s: %d filas, %d SKU distintos%s%s", nombre, ruta.name, v.filas,
                         v.skus_distintos, f" · ERRORES: {'; '.join(errores)}" if errores else "",
                         f" · avisos: {'; '.join(avisos)}" if avisos else "")
        return self.cache[nombre]


def main() -> None:
    ap = argparse.ArgumentParser(description="Sube inventarios (CSV) a proveedores del MKP")
    ap.add_argument("--mkp", help=f"Clave del marketplace: {', '.join(MARKETPLACES)}")
    ap.add_argument("--excel", help="Ruta del Excel (por defecto 'Enlaces por nombre.xlsx')")
    ap.add_argument("--validar", action="store_true", help="Solo revisa el Excel y los CSV (sin conectarse)")
    ap.add_argument("--convertir", metavar="XLSX", help="Regenera Inventarios/<nombre>.csv desde un .xlsx")
    ap.add_argument("--diagnose", action="store_true", help="Revisa el formulario de importación sin subir")
    ap.add_argument("--verificar", action="store_true", help="Confirma en el panel las filas EN PROCESO")
    ap.add_argument("--limit", type=int, default=0, help="Máximo de proveedores a procesar")
    ap.add_argument("--filas", help="Rango de filas del Excel, ej. 5-10")
    ap.add_argument("--espera", type=int, default=ESPERA_PROCESO,
                    help=f"Segundos a esperar el procesamiento de cada CSV (por defecto {ESPERA_PROCESO})")
    ap.add_argument("--forzar", action="store_true",
                    help="Sube aunque el CSV tenga errores (p. ej. SKU en notación científica). No recomendado")
    args = ap.parse_args()

    # ── Conversión xlsx → csv (no se conecta) ──
    if args.convertir:
        configurar_log("convertir")
        origen = Path(args.convertir)
        origen = origen if origen.is_absolute() or origen.exists() else RAIZ / origen
        destino = INVENTARIOS_DIR / f"{origen.stem}.csv"
        if destino.exists() and not args.forzar:
            raise SystemExit(f"Ya existe {destino.name}; usa --forzar para reemplazarlo.")
        convertir_xlsx(origen, destino)
        v = validar_csv(destino)
        log.info("Generado %s: %d filas, %d SKU distintos%s", destino, v.filas, v.skus_distintos,
                 f" · ERRORES: {'; '.join(v.errores)}" if v.errores else " · sin errores")
        log.info("Pon '%s' en la columna Name_inventario del Excel.", destino.name)
        return

    cargar_dotenv()
    mkp = "EXCEL" if args.validar and not args.mkp else elegir_mkp(args.mkp)
    ruta_log = configurar_log(mkp)
    excel = Path(args.excel).resolve() if args.excel else EXCEL_DEFAULT
    libro = LibroEnlaces(excel, mkp)
    filas = libro.filas()
    if args.filas:
        a, _, b = args.filas.partition("-")
        filas = [f for f in filas if int(a) <= f.fila <= int(b or a)]
    log.info("Excel: %s — %d proveedores", excel.name, len(filas))
    archivos = Archivos(args.forzar)
    for nombre in dict.fromkeys(f.archivo for f in filas if f.archivo):
        archivos.revisar(nombre)
    if args.validar:
        malas = sum(1 for f in filas if f.errores or archivos.revisar(f.archivo)[1])
        log.info("Filas listas para subir: %d · con problemas: %d", len(filas) - malas, malas)
        return

    from mkp import ClienteFAD, ErrorMKP

    url, usuario, password = credenciales(mkp)
    cli = ClienteFAD(url, log)
    cli.login(usuario, password)
    indice = cli.proveedores()
    log.info("Proveedores en el panel: %d", len(indice))

    if args.diagnose:
        _diagnosticar(cli, indice, filas, LOGS_DIR / f"diag_{mkp}")
        return
    log.info("Respaldo del Excel: %s", libro.respaldar().name)

    resumen: dict[str, int] = {}
    procesados = fallos_seguidos = 0
    try:
        for f in filas:
            if args.limit and procesados >= args.limit:
                break
            previo = libro.estado(f.fila)
            if args.verificar:
                if previo != EN_PROCESO:
                    continue
            else:
                if f.errores:
                    _registrar(libro, f, DATOS_INVALIDOS, "; ".join(f.errores), resumen)
                    continue
                if previo in ESTADOS_TERMINADOS:
                    log.info("  fila %d %-35s ya marcado %s, se omite", f.fila, f.nombre, previo)
                    continue
            procesados += 1
            log.info("▶ fila %d  %s  ←  %s", f.fila, f.nombre, f.archivo)
            try:
                if args.verificar:
                    _verificar(cli, indice, libro, f, resumen)
                else:
                    _subir(cli, indice, archivos, libro, f, resumen, args.espera, ErrorMKP)
                fallos_seguidos = 0
            except Exception as e:
                fallos_seguidos += 1
                _registrar(libro, f, ERROR, f"Error inesperado: {str(e).splitlines()[0] if str(e) else e.__class__.__name__}", resumen)
                if fallos_seguidos >= 5:
                    log.info("5 errores inesperados seguidos: se detiene la corrida para revisar.")
                    break
    except KeyboardInterrupt:
        log.info("Interrumpido por el usuario. Lo procesado ya está guardado en el Excel.")

    log.info("─" * 60)
    log.info("Resumen %s: %s", mkp, ", ".join(f"{k}: {v}" for k, v in resumen.items()) or "nada que procesar")
    if resumen.get(EN_PROCESO):
        log.info("Hay filas EN PROCESO: confírmalas más tarde con  py src\\main.py --mkp %s --verificar", mkp)
    log.info("Resultados en: %s", libro.destino)
    if libro.destino != libro.ruta:
        log.info("(El Excel original estaba abierto; ciérralo la próxima vez para escribir directo en él.)")
    log.info("Log: %s", ruta_log)


def _buscar(indice, nombre):
    exactas = [p for p in indice if p["nombre"] == nombre]
    parecidas = [p for p in indice if p["nombre"] != nombre and (
        norm(p["nombre"]) == norm(nombre) or norm(nombre) in norm(p["nombre"])
        or (norm(p["nombre"]) and norm(p["nombre"]) in norm(nombre)))]
    return exactas, parecidas


def _proveedor_unico(indice, libro, f, resumen):
    exactas, parecidas = _buscar(indice, f.nombre)
    if not exactas:
        obs = "No hay un proveedor con ese nombre exacto en el panel; no se subió"
        if parecidas:
            obs += ". Parecidos: " + ", ".join(f"'{p['nombre']}'" for p in parecidas[:5])
        _registrar(libro, f, NO_ENCONTRADO, obs, resumen)
        return None
    if len(exactas) > 1:
        _registrar(libro, f, ERROR, f"Hay {len(exactas)} proveedores con ese mismo nombre; "
                                    "no se subió para no equivocar la tienda", resumen)
        return None
    return exactas[0]


def _subir(cli, indice, archivos, libro, f, resumen, espera, ErrorMKP) -> None:
    ruta, errores, avisos = archivos.revisar(f.archivo)
    if errores:
        _registrar(libro, f, DATOS_INVALIDOS, "CSV no apto: " + "; ".join(errores), resumen)
        return
    prov = _proveedor_unico(indice, libro, f, resumen)
    if prov is None:
        return
    try:
        sub = cli.con_reintento(cli.importar_csv, prov["id"], ruta)
    except ErrorMKP as e:
        _registrar(libro, f, ERROR, str(e), resumen)
        return
    antes = sub["antes"]
    previos = {h["archivo"] for h in antes["historial"]}
    log.info("   subido; el panel respondió: %s", sub["respuesta"].get("message") or "success")

    # ── Validador: el archivo debe aparecer en el historial y terminar en éxito ──
    res = cli.esperar_importacion(prov["id"], ruta.name, previos, espera, INTERVALO_SONDEO)
    notas = list(avisos)
    t0, t1 = antes["total_servicios"], res["pag"]["total_servicios"]
    if t0 is not None and t1 is not None:
        notas.append(f"Total Servicios: {t0} → {t1}")
    fila_h = res["fila"]
    if fila_h and fila_h.get("estado"):
        notas.append(f"Estado en el panel: '{fila_h['estado']}'")
    if res["estado"] == "OK":
        _registrar(libro, f, OK, "; ".join(notas), resumen)
    elif res["estado"] == "ERROR":
        if fila_h and fila_h.get("errores"):
            notas.append(f"Errores: {fila_h['errores']}")
        if fila_h and fila_h.get("enlace"):
            notas.append(f"Detalle: {fila_h['enlace']}")
        _registrar(libro, f, ERROR, "El panel marcó la importación con error; " + "; ".join(notas), resumen)
    elif res["estado"] == "EN PROCESO":
        _registrar(libro, f, EN_PROCESO, "Subido; el panel lo sigue procesando. " + "; ".join(notas), resumen)
    else:   # SIN REGISTRO: aceptado pero no aparece en el historial
        _registrar(libro, f, EN_PROCESO, "El panel aceptó el archivo pero aún no aparece en el historial de "
                                         "importaciones. " + "; ".join(notas), resumen)
    time.sleep(0.3)


def _verificar(cli, indice, libro, f, resumen) -> None:
    prov = _proveedor_unico(indice, libro, f, resumen)
    if prov is None:
        return
    pag = cli.con_reintento(cli.pagina_catalogo, prov["id"])
    from mkp import clasificar_estado
    from inventario import resolver_archivo as _res
    ruta, _ = _res(f.archivo)
    nombre = ruta.name if ruta else f.archivo
    fila_h = next((h for h in pag["historial"] if h["archivo"].endswith(nombre)), None)
    if not fila_h:
        _registrar(libro, f, EN_PROCESO, "Aún no aparece en el historial de importaciones", resumen)
        return
    estado = clasificar_estado(fila_h["estado"])
    obs = f"Estado en el panel: '{fila_h['estado']}'; Total Servicios: {pag['total_servicios']}"
    if estado == "ERROR" and fila_h.get("errores"):
        obs += f"; Errores: {fila_h['errores']}"
    if estado == "ERROR" and fila_h.get("enlace"):
        obs += f"; Detalle: {fila_h['enlace']}"
    _registrar(libro, f, estado, obs, resumen)


def _diagnosticar(cli, indice, filas, carpeta: Path) -> None:
    carpeta.mkdir(parents=True, exist_ok=True)
    f = next((x for x in filas if not x.errores and len(_buscar(indice, x.nombre)[0]) == 1), None)
    if f is None:
        log.info("Ninguna fila del Excel tiene un proveedor con nombre exacto único en el panel.")
        return
    prov = _buscar(indice, f.nombre)[0][0]
    log.info("Proveedor de prueba: '%s' (id %s, %s)", prov["nombre"], prov["id"], prov["pestana"])
    pag = cli.pagina_catalogo(prov["id"])
    (carpeta / "diag_catalogo.html").write_text(pag["html"], encoding="utf-8")
    log.info("Formulario de importación (#save_imported_products): %s", "encontrado" if pag["form"] else "NO encontrado")
    log.info("Campo del archivo: %s", pag["campo_archivo"] or "NO encontrado")
    log.info("Otros campos que se envían: %s", sorted(k for k in pag["campos"]) or "ninguno")
    log.info("Token CSRF: %s", "encontrado" if pag["csrf"] else "NO encontrado")
    log.info("Total Servicios: %s", pag["total_servicios"])
    log.info("Historial de importaciones: %d registros. Últimos: %s", len(pag["historial"]),
             [(h["archivo"], h["estado"]) for h in pag["historial"][:3]] or "ninguno")
    log.info("Diagnóstico guardado en %s (no se subió ningún archivo).", carpeta)


def _registrar(libro, f, estado: str, obs: str, resumen: dict) -> None:
    libro.marcar(f.fila, estado, obs)
    resumen[estado] = resumen.get(estado, 0) + 1
    log.info("  fila %d %-35s %s%s", f.fila, f.nombre, estado, f" — {obs}" if obs else "")


if __name__ == "__main__":
    main()
