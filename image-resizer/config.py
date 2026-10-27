"""
config.py
=========
Configuración central del proyecto image-resizer.

Estos son los valores por defecto pensados para el servidor de
Full Farma / Farmacia Quetzal (Windows + Tomcat9). Todos pueden
sobreescribirse desde la línea de comandos al ejecutar main.py, así
que normalmente no necesitas tocar este archivo: solo ajusta aquí lo
que quieras que sea el comportamiento estándar.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------
# Raíz del proyecto (carpeta donde vive este archivo).
PROJECT_ROOT = Path(__file__).resolve().parent

# Carpeta de ENTRADA: aquí pones las imágenes originales a procesar.
# NO se modifican ni se sobreescriben nunca. Por defecto es la carpeta
# "inputs" dentro del proyecto, para que funcione igual en tu PC local
# que en el servidor sin cambiar rutas.
SOURCE_DIR = PROJECT_ROOT / "inputs"

# Carpeta de SALIDA: aquí se guardan las imágenes redimensionadas.
# Separada de la entrada para no mezclar resultados con los originales.
OUTPUT_DIR = PROJECT_ROOT / "outputs"

# Si True, los resultados se guardan en una subcarpeta por tamaño
# (p. ej. outputs/540x715/, outputs/800x800/) para que lotes de distintas
# dimensiones no se pisen entre sí. Cada tamaño tiene su propio manifiesto.
SEPARATE_OUTPUT_BY_SIZE = True

# ---------------------------------------------------------------------------
# Dimensiones de destino
# ---------------------------------------------------------------------------
# Tamaño por defecto (requisito de farmaciasdomicilio.mx).
TARGET_WIDTH = 540
TARGET_HEIGHT = 715

# Presets de tamaño que ofrece el menú. Para agregar otro marketplace,
# solo añade un diccionario más a esta lista. El primero es el default.
PRESETS = [
    {"nombre": "farmaciasdomicilio.mx", "width": 540, "height": 715},
]

# ---------------------------------------------------------------------------
# Apariencia del lienzo
# ---------------------------------------------------------------------------
# Color de relleno (padding). Blanco puro por defecto: (R, G, B).
BACKGROUND_COLOR = (255, 255, 255)

# Margen interior opcional en píxeles: deja un aire alrededor del producto
# para que no toque los bordes del lienzo. 0 = sin margen.
PADDING = 0

# ---------------------------------------------------------------------------
# Salida JPEG
# ---------------------------------------------------------------------------
# Calidad de compresión JPEG (1-95 recomendado). 90 = buena calidad/peso.
JPEG_QUALITY = 90

# Optimizar el archivo JPEG resultante (recomienda tablas Huffman óptimas).
JPEG_OPTIMIZE = True

# Guardar como JPEG progresivo (carga más agradable en la web).
JPEG_PROGRESSIVE = True

# Extensiones de imagen que se procesarán (en minúsculas).
VALID_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

# ---------------------------------------------------------------------------
# Rendimiento y comportamiento del lote
# ---------------------------------------------------------------------------
# Número de hilos de trabajo. None = usar (núcleos de CPU) automáticamente.
MAX_WORKERS = None

# Si True, no se vuelve a procesar una imagen cuyo resultado ya existe
# en OUTPUT_DIR (permite reanudar un lote interrumpido sin repetir trabajo).
SKIP_EXISTING = True

# ---------------------------------------------------------------------------
# Publicación / manifiesto
# ---------------------------------------------------------------------------
# URL pública base desde la que Tomcat sirve las imágenes. Se usa para
# generar un manifiesto CSV (SKU -> URL) que puedes cruzar con tu catálogo.
PUBLIC_BASE_URL = "https://fullfarma.mx/Images/"

# Nombre del archivo de manifiesto CSV generado dentro de OUTPUT_DIR.
MANIFEST_FILENAME = "manifest.csv"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
# Archivo de log (dentro del proyecto). Se registra todo lo procesado y los
# errores por imagen, sin detener el lote completo.
LOG_FILE = Path(__file__).resolve().parent / "image-resizer.log"
