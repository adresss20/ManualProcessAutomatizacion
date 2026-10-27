"""
main.py
=======
Orquestador del proyecto image-resizer para Full Farma / Farmacia Quetzal.

Redimensiona en lote las imágenes del catálogo al formato que exige el
marketplace farmaciasdomicilio.mx (540x715 px), sin deformar el producto:
mantiene la proporción, centra la imagen y rellena con fondo blanco.

  - Entrada:  carpeta  inputs/   (pon aquí tus imágenes)
  - Salida:   carpeta  outputs/  (aquí aparecen los resultados)

FORMA FÁCIL (recomendada): solo ejecuta
    python main.py
...y aparece un MENÚ que te pregunta qué quieres hacer, mostrando el
estado del sistema (cuántas imágenes hay, dependencias, carpetas).

FORMA AVANZADA (línea de comandos), para automatizar:
    python main.py --manifest
    python main.py --dry-run --verbose
    python main.py --test
    python main.py --help    (ver todas las opciones)
"""

import argparse
import logging
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# La consola de Windows (cmd/PowerShell) suele usar cp1252 y no puede mostrar
# acentos ni símbolos. Forzamos UTF-8 en la salida para que se vea bien y no
# truene al imprimir caracteres como "✓" o "ñ".
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 - versiones/entornos sin reconfigure
        pass

from PIL import Image, ImageFile

import config
from modules import file_handler
from modules.resizer import resize_with_padding

# Tolerar archivos JPEG ligeramente truncados en lugar de reventar el lote.
ImageFile.LOAD_TRUNCATED_IMAGES = True

# Intentar barra de progreso bonita; si no está tqdm, se degrada con gracia.
try:
    from tqdm import tqdm

    _HAS_TQDM = True
except ImportError:  # pragma: no cover
    _HAS_TQDM = False


logger = logging.getLogger("image-resizer")


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def setup_logging(log_file: Path, verbose: bool) -> None:
    """Configura logging a consola y a archivo."""
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")

    file_log = logging.FileHandler(log_file, encoding="utf-8")
    file_log.setLevel(logging.DEBUG)
    file_log.setFormatter(fmt)
    logger.addHandler(file_log)

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG if verbose else logging.WARNING)
    console.setFormatter(fmt)
    logger.addHandler(console)


# ---------------------------------------------------------------------------
# Argumentos de línea de comandos (uso avanzado / automatización)
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Redimensiona imágenes de catálogo a un tamaño fijo "
        "sin deformarlas (proporción + centrado + fondo blanco). "
        "Ejecuta sin argumentos para abrir el menú interactivo.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--source", type=Path, default=config.SOURCE_DIR,
                   help="Carpeta con las imágenes originales.")
    p.add_argument("--output", type=Path, default=config.OUTPUT_DIR,
                   help="Carpeta donde se guardan los resultados.")
    p.add_argument("--width", type=int, default=config.TARGET_WIDTH,
                   help="Ancho de destino en píxeles.")
    p.add_argument("--height", type=int, default=config.TARGET_HEIGHT,
                   help="Alto de destino en píxeles.")
    p.add_argument("--quality", type=int, default=config.JPEG_QUALITY,
                   help="Calidad JPEG (1-95).")
    p.add_argument("--padding", type=int, default=config.PADDING,
                   help="Margen interior en píxeles alrededor del producto.")
    p.add_argument("--bg", type=str, default=None,
                   help='Color de fondo "R,G,B" (por defecto blanco 255,255,255).')
    p.add_argument("--workers", type=int, default=config.MAX_WORKERS,
                   help="Número de hilos (por defecto: núcleos de CPU).")

    skip = p.add_mutually_exclusive_group()
    skip.add_argument("--skip-existing", dest="skip_existing", action="store_true",
                      default=config.SKIP_EXISTING,
                      help="Saltar imágenes ya generadas (reanudar).")
    skip.add_argument("--overwrite", dest="skip_existing", action="store_false",
                      help="Reprocesar todo aunque ya exista el resultado.")

    p.add_argument("--manifest", action="store_true",
                   help="Generar manifiesto CSV (sku, archivo, url) al terminar.")
    p.add_argument("--dry-run", action="store_true",
                   help="Simular: mostrar qué se haría sin escribir archivos.")
    p.add_argument("--test", action="store_true",
                   help="Prueba de salud: procesa imágenes de ejemplo y verifica todo.")
    p.add_argument("--menu", action="store_true",
                   help="Forzar el menú interactivo aunque se pasen otros argumentos.")
    p.add_argument("--verbose", "-v", action="store_true",
                   help="Mostrar detalle por imagen en consola.")
    return p


def parse_bg(value):
    """Convierte 'R,G,B' en una tupla; usa el default de config si es None."""
    if not value:
        return config.BACKGROUND_COLOR
    try:
        parts = tuple(int(x) for x in value.split(","))
        if len(parts) != 3 or any(not 0 <= c <= 255 for c in parts):
            raise ValueError
        return parts
    except ValueError:
        raise SystemExit(f"Color de fondo inválido: '{value}'. Usa formato R,G,B (0-255).")


# ---------------------------------------------------------------------------
# Procesamiento
# ---------------------------------------------------------------------------
def process_one(src: Path, args, bg) -> tuple:
    """Procesa una sola imagen. Devuelve (estado, nombre, mensaje).

    estado ∈ {"ok", "skip", "error"}. Nunca lanza: los errores se capturan
    para que una imagen corrupta no detenga el lote completo.
    """
    out = file_handler.output_path_for(src, args.output)
    try:
        if file_handler.should_skip(src, args.output, args.skip_existing):
            logger.debug("SALTADA (ya existe): %s", src.name)
            return ("skip", out.name, "")

        if args.dry_run:
            logger.debug("[dry-run] procesaría %s -> %s", src.name, out.name)
            return ("ok", out.name, "")

        with Image.open(src) as im:
            result = resize_with_padding(
                im, args.width, args.height, background_color=bg, padding=args.padding
            )
            result.save(
                out,
                format="JPEG",
                quality=args.quality,
                optimize=config.JPEG_OPTIMIZE,
                progressive=config.JPEG_PROGRESSIVE,
            )
        logger.debug("OK: %s -> %s", src.name, out.name)
        return ("ok", out.name, "")

    except Exception as exc:  # noqa: BLE001 - queremos capturar todo por imagen
        logger.error("ERROR en %s: %s", src.name, exc)
        return ("error", src.name, str(exc))


def effective_output(base_output: Path, width: int, height: int) -> Path:
    """Ruta de salida real, con subcarpeta por tamaño si está activado.

    Solo se anida cuando la salida es la carpeta por defecto (config.OUTPUT_DIR);
    si el usuario pasó un --output explícito, se respeta tal cual.
    """
    if base_output == config.OUTPUT_DIR and config.SEPARATE_OUTPUT_BY_SIZE:
        return base_output / f"{width}x{height}"
    return base_output


def run_batch(args, bg) -> int:
    """Ejecuta el lote completo con la configuración de `args`. Devuelve exit code."""
    args.output = effective_output(args.output, args.width, args.height)
    print("=" * 60)
    print("  image-resizer  ·  Full Farma / Farmacia Quetzal")
    print("=" * 60)
    print(f"  Entrada : {args.source}")
    print(f"  Salida  : {args.output}")
    print(f"  Tamaño  : {args.width}x{args.height} px  (fondo {bg})")
    print(f"  Modo    : {'SIMULACIÓN (dry-run)' if args.dry_run else 'REAL'}"
          f"  ·  {'reanudable' if args.skip_existing else 'sobreescribe'}")
    print("=" * 60)

    try:
        images = file_handler.discover_images(args.source, config.VALID_EXTENSIONS)
    except (FileNotFoundError, NotADirectoryError) as exc:
        print(f"\n[ERROR] {exc}")
        return 1

    if not images:
        print(f"\nNo hay imágenes en la carpeta de entrada:\n  {args.source}")
        print("Copia ahí tus imágenes (.jpg, .png, .webp...) y vuelve a ejecutar.")
        return 0

    print(f"\nSe encontraron {len(images)} imágenes.\n")

    if not args.dry_run:
        file_handler.ensure_output_dir(args.output)

    counts = {"ok": 0, "skip": 0, "error": 0}
    errors = []
    processed_names = []
    start = time.time()

    def iterator(futures):
        if _HAS_TQDM:
            return tqdm(as_completed(futures), total=len(futures), unit="img")
        return as_completed(futures)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(process_one, src, args, bg): src for src in images}
        for fut in iterator(futures):
            status, name, msg = fut.result()
            counts[status] += 1
            if status == "ok":
                processed_names.append(name)
            elif status == "error":
                errors.append((name, msg))

    elapsed = time.time() - start

    manifest_path = None
    if args.manifest and not args.dry_run:
        existing = [p.name for p in args.output.glob("*.jpg")]
        if existing:
            manifest_path = file_handler.write_manifest(
                existing, args.output,
                config.MANIFEST_FILENAME, config.PUBLIC_BASE_URL,
            )

    print("\n" + "=" * 60)
    print("  RESUMEN")
    print("=" * 60)
    print(f"  Procesadas : {counts['ok']}")
    print(f"  Saltadas   : {counts['skip']}")
    print(f"  Fallidas   : {counts['error']}")
    if elapsed > 0:
        print(f"  Tiempo     : {elapsed:.1f} s ({len(images) / elapsed:.1f} img/s)")
    if manifest_path:
        print(f"  Manifiesto : {manifest_path}")
    print(f"  Log        : {config.LOG_FILE}")
    print("=" * 60)

    if errors:
        print(f"\nSe registraron {len(errors)} errores (ver log). Primeros:")
        for name, msg in errors[:10]:
            print(f"  - {name}: {msg}")

    return 1 if counts["error"] else 0


# ---------------------------------------------------------------------------
# Modo prueba (--test): verifica que todo el pipeline funciona
# ---------------------------------------------------------------------------
def run_test(args, bg) -> int:
    """Genera imágenes de ejemplo, las procesa y verifica el resultado.

    No toca tus carpetas inputs/outputs: usa una carpeta temporal.
    Sirve para confirmar que la instalación funciona correctamente.
    """
    print("=" * 60)
    print("  MODO PRUEBA  ·  verificación del sistema")
    print("=" * 60)

    tmp = Path(tempfile.mkdtemp(prefix="image-resizer-test-"))
    src_dir = tmp / "in"
    out_dir = tmp / "out"
    src_dir.mkdir()

    # Casos representativos: cuadrada (como las reales), vertical, y PNG con alfa.
    samples = {
        "cuadrada_551.jpg": Image.new("RGB", (551, 551), (200, 40, 40)),
        "vertical_400x900.jpg": Image.new("RGB", (400, 900), (40, 120, 200)),
    }
    png = Image.new("RGBA", (600, 300), (0, 180, 0, 255))
    for name, im in samples.items():
        im.save(src_dir / name)
    png.save(src_dir / "transparente.png")
    print(f"  Se crearon {len(samples) + 1} imágenes de ejemplo.")

    test_args = argparse.Namespace(**vars(args))
    test_args.source = src_dir
    test_args.output = out_dir
    test_args.dry_run = False
    test_args.skip_existing = False
    test_args.manifest = False
    test_args.verbose = False

    file_handler.ensure_output_dir(out_dir)
    ok = err = 0
    for src in file_handler.discover_images(src_dir, config.VALID_EXTENSIONS):
        status, _, _ = process_one(src, test_args, bg)
        ok += status == "ok"
        err += status == "error"

    # Verificar dimensiones exactas.
    all_correct = True
    for f in sorted(out_dir.glob("*.jpg")):
        w, h = Image.open(f).size
        mark = "OK " if (w, h) == (args.width, args.height) else "MAL"
        if mark == "MAL":
            all_correct = False
        print(f"    [{mark}] {f.name}: {w}x{h}")

    # Limpieza.
    for f in src_dir.iterdir():
        f.unlink()
    for f in out_dir.iterdir():
        f.unlink()
    out_dir.rmdir()
    src_dir.rmdir()
    tmp.rmdir()

    print("=" * 60)
    passed = err == 0 and all_correct and ok > 0
    print(f"  RESULTADO: {'✓ TODO CORRECTO' if passed else '✗ HAY PROBLEMAS'}"
          f"  (procesadas {ok}, errores {err})")
    print("=" * 60)
    return 0 if passed else 1


# ---------------------------------------------------------------------------
# Menú interactivo (uso fácil, sin memorizar flags)
# ---------------------------------------------------------------------------
def count_input_images(source: Path) -> int:
    try:
        return len(file_handler.discover_images(source, config.VALID_EXTENSIONS))
    except (FileNotFoundError, NotADirectoryError):
        return 0


def print_status(args) -> int:
    """Muestra el estado del sistema. Devuelve cuántas imágenes hay en entrada."""
    n_in = count_input_images(args.source)
    # La salida se organiza en subcarpetas por tamaño, así que contamos recursivo.
    n_out = len(list(args.output.rglob("*.jpg"))) if args.output.exists() else 0
    deps = "OK (Pillow + tqdm)" if _HAS_TQDM else "Pillow OK, tqdm NO (progreso simple)"

    print("=" * 60)
    print("  image-resizer  ·  Full Farma / Farmacia Quetzal")
    print("=" * 60)
    print("  ESTADO DEL SISTEMA")
    print(f"    Carpeta de entrada : {args.source}")
    print(f"        -> imágenes encontradas: {n_in}")
    print(f"    Carpeta de salida  : {args.output}")
    print(f"        -> ya procesadas (todos los tamaños): {n_out}")
    print(f"    Dependencias       : {deps}")
    print("    (el tamaño se elige al procesar; resultados separados por tamaño)")
    print("=" * 60)
    return n_in


def _ask_int(prompt: str):
    """Pide un entero positivo y sensato (1-20000). Devuelve int o None si cancela."""
    while True:
        raw = input(prompt).strip()
        if raw == "":
            return None
        try:
            value = int(raw)
        except ValueError:
            print("    Escribe solo números (sin letras ni símbolos).")
            continue
        if not 1 <= value <= 20000:
            print("    Valor fuera de rango. Usa un número entre 1 y 20000.")
            continue
        return value


def choose_dimensions():
    """Pregunta el tamaño de destino. Devuelve (ancho, alto) o None si se cancela.

    Ofrece los presets de config.PRESETS (el primero es el default, con Enter)
    y una opción personalizada con validación.
    """
    print("\n  ¿A qué tamaño quieres las imágenes?\n")
    for i, preset in enumerate(config.PRESETS, start=1):
        marca = "  [Enter = default]" if i == 1 else ""
        print(f"    [{i}] {preset['nombre']}"
              f"  →  {preset['width']} x {preset['height']} px{marca}")
    custom_opt = len(config.PRESETS) + 1
    print(f"    [{custom_opt}] Personalizado (escribir ancho y alto)")
    print("    [0] Cancelar")

    choice = input("\n  Tamaño > ").strip()

    if choice == "":  # Enter = primer preset (farmaciasdomicilio).
        p = config.PRESETS[0]
        return (p["width"], p["height"])
    if choice == "0":
        return None
    if choice.isdigit() and 1 <= int(choice) <= len(config.PRESETS):
        p = config.PRESETS[int(choice) - 1]
        return (p["width"], p["height"])
    if choice == str(custom_opt):
        print()
        w = _ask_int("    Ancho en píxeles (Enter para cancelar) > ")
        if w is None:
            return None
        h = _ask_int("    Alto en píxeles  (Enter para cancelar) > ")
        if h is None:
            return None
        return (w, h)

    print("  Opción de tamaño no válida.")
    return None


def interactive_menu(parser: argparse.ArgumentParser) -> int:
    """Menú de texto. Traduce la elección del usuario a la acción correcta."""
    base = parser.parse_args([])  # Namespace con todos los defaults.
    bg = parse_bg(base.bg)

    while True:
        n_in = print_status(base)

        print("\n  ¿Qué quieres hacer?\n")
        print("    [1] Redimensionar imágenes (normal, reanudable)")
        print("    [2] Redimensionar + generar manifiesto CSV (sku -> URL)")
        print("    [3] Simular sin escribir nada (vista previa / dry-run)")
        print("    [4] Reprocesar TODO de nuevo (sobreescribe resultados)")
        print("    [5] Probar el sistema con imágenes de ejemplo (--test)")
        print("    [6] Abrir la carpeta de entrada (dónde poner las imágenes)")
        print("    [0] Salir")

        try:
            choice = input("\n  Opción > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nHasta luego.")
            return 0

        # Reconstruimos un Namespace fresco desde los defaults en cada acción.
        args = parser.parse_args([])

        if choice == "1":
            dims = choose_dimensions()
            if dims is None:
                print("  Cancelado.\n")
                continue
            args.width, args.height = dims
            return run_batch(args, bg)
        elif choice == "2":
            dims = choose_dimensions()
            if dims is None:
                print("  Cancelado.\n")
                continue
            args.width, args.height = dims
            args.manifest = True
            return run_batch(args, bg)
        elif choice == "3":
            dims = choose_dimensions()
            if dims is None:
                print("  Cancelado.\n")
                continue
            args.width, args.height = dims
            args.dry_run = True
            args.verbose = True
            return run_batch(args, bg)
        elif choice == "4":
            dims = choose_dimensions()
            if dims is None:
                print("  Cancelado.\n")
                continue
            args.width, args.height = dims
            confirm = input(f"  Esto sobreescribe lo ya procesado en "
                            f"{args.width}x{args.height}. ¿Seguro? (s/N) > ")
            if confirm.strip().lower() in ("s", "si", "sí"):
                args.skip_existing = False
                args.manifest = True
                return run_batch(args, bg)
            print("  Cancelado.\n")
        elif choice == "5":
            run_test(args, bg)
            input("\n  Enter para volver al menú...")
        elif choice == "6":
            file_handler.ensure_output_dir(base.source)  # crea inputs si falta
            print(f"\n  Pon tus imágenes en:\n    {base.source}")
            _open_folder(base.source)
            input("\n  Enter para volver al menú (y actualizar el conteo)...")
        elif choice == "0":
            print("\nHasta luego.")
            return 0
        else:
            print("  Opción no válida.\n")


def _open_folder(path: Path) -> None:
    """Abre la carpeta en el explorador (Windows/Mac/Linux); ignora si no puede."""
    try:
        import os
        import subprocess

        if sys.platform.startswith("win"):
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------
# Entrada
# ---------------------------------------------------------------------------
def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    setup_logging(config.LOG_FILE, args.verbose)

    # Sin argumentos (o con --menu) -> menú interactivo.
    only_defaults = len(sys.argv) == 1
    if only_defaults or args.menu:
        return interactive_menu(parser)

    bg = parse_bg(args.bg)
    if args.test:
        return run_test(args, bg)
    return run_batch(args, bg)


if __name__ == "__main__":
    raise SystemExit(main())
