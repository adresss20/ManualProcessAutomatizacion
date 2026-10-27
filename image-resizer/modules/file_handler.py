"""
file_handler.py
===============
Todo lo relacionado con el disco: descubrir imágenes de origen, calcular
rutas de salida, decidir si algo se puede saltar y escribir el manifiesto
CSV que relaciona cada SKU con su URL pública.

Separar esto de la lógica de imagen mantiene resizer.py testeable y puro.
"""

import csv
from pathlib import Path


def discover_images(source_dir: Path, valid_extensions: set) -> list:
    """Lista los archivos de imagen dentro de source_dir (no recursivo).

    Devuelve una lista ordenada de Path. La comparación de extensión es
    insensible a mayúsculas (.JPG y .jpg cuentan igual).
    """
    if not source_dir.exists():
        raise FileNotFoundError(f"No existe la carpeta de origen: {source_dir}")
    if not source_dir.is_dir():
        raise NotADirectoryError(f"La ruta de origen no es una carpeta: {source_dir}")

    files = [
        p
        for p in source_dir.iterdir()
        if p.is_file() and p.suffix.lower() in valid_extensions
    ]
    return sorted(files)


def output_path_for(source_file: Path, output_dir: Path) -> Path:
    """Ruta de salida para una imagen dada.

    Conserva el nombre (el SKU) y fuerza la extensión .jpg, porque el
    resultado siempre se guarda como JPEG.
    """
    return output_dir / f"{source_file.stem}.jpg"


def ensure_output_dir(output_dir: Path) -> None:
    """Crea la carpeta de salida si no existe (incluye padres)."""
    output_dir.mkdir(parents=True, exist_ok=True)


def should_skip(source_file: Path, output_dir: Path, skip_existing: bool) -> bool:
    """True si ya existe un resultado válido y se pidió reanudar.

    Se considera válido si el archivo de salida existe y no está vacío.
    """
    if not skip_existing:
        return False
    out = output_path_for(source_file, output_dir)
    return out.exists() and out.stat().st_size > 0


def write_manifest(rows: list, output_dir: Path, filename: str, base_url: str) -> Path:
    """Escribe un CSV (sku, archivo, url) con las imágenes procesadas.

    `rows` es una lista de nombres de archivo de salida (p. ej. "51131000230.jpg").
    Sirve para cruzar con el catálogo y llenar la columna de imagen del CSV
    del marketplace sin construir las URLs a mano.
    """
    base = base_url if base_url.endswith("/") else base_url + "/"
    manifest = output_dir / filename
    with manifest.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["sku", "archivo", "url"])
        for name in sorted(rows):
            sku = Path(name).stem
            writer.writerow([sku, name, f"{base}{name}"])
    return manifest
