# image-resizer

Redimensiona en lote las imágenes del catálogo de **Full Farma / Farmacia Quetzal**
al formato que exige el marketplace `farmaciasdomicilio.mx` (**540×715 px**), sin
deformar el producto: mantiene la proporción original, centra la imagen y rellena el
espacio sobrante con fondo blanco. Los originales **no** se modifican.

Pones tus imágenes en la carpeta **`inputs/`** y los resultados aparecen en
**`outputs/`**. Funciona igual en tu PC local que en el servidor.

---

## 1. Dependencias

- **Python 3.8+**
- **Pillow** — procesamiento de imágenes
- **tqdm** — barra de progreso (opcional; el script funciona sin ella)

Listadas en [`requirements.txt`](requirements.txt).

---

## 2. Instalación

Desde la carpeta del proyecto, en PowerShell o CMD del servidor Windows:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

---

## 3. Configuración

No necesitas configurar nada para empezar: solo copia tus imágenes en `inputs/`.
Si quieres cambiar los valores por defecto, edita [`config.py`](config.py):

| Variable | Descripción | Valor por defecto |
|---|---|---|
| `SOURCE_DIR` | Carpeta de entrada | `.\inputs` |
| `OUTPUT_DIR` | Carpeta de salida | `.\outputs` |
| `TARGET_WIDTH` × `TARGET_HEIGHT` | Tamaño de destino | `540 × 715` |
| `BACKGROUND_COLOR` | Color de relleno | blanco `(255,255,255)` |
| `JPEG_QUALITY` | Calidad de compresión | `90` |
| `SKIP_EXISTING` | Reanudar sin repetir lo ya hecho | `True` |
| `PUBLIC_BASE_URL` | Base para el manifiesto CSV | `https://fullfarma.mx/Images/` |

Cualquier valor puede sobreescribirse al vuelo con argumentos de línea de comandos
(`--source`, `--output`, `--width`, `--height`, `--quality`, `--bg`, `--workers`,
`--overwrite`, `--manifest`, `--dry-run`, `--test`, `--verbose`). Ver `python main.py --help`.

---

## 4. Comando para ejecutar en Windows

**Forma fácil (recomendada).** Con el entorno virtual activado, desde la carpeta
del proyecto, ejecuta simplemente:

```bash
python main.py
```

Aparece un **menú** que muestra el estado del sistema (cuántas imágenes hay en
`inputs/`, dependencias, carpetas) y te deja elegir qué hacer:

```
[1] Redimensionar imágenes (normal, reanudable)
[2] Redimensionar + generar manifiesto CSV (sku -> URL)
[3] Simular sin escribir nada (vista previa / dry-run)
[4] Reprocesar TODO de nuevo (sobreescribe resultados)
[5] Probar el sistema con imágenes de ejemplo (--test)
[6] Abrir la carpeta de entrada
[0] Salir
```

**Forma avanzada (opcional).** Para automatizar, puedes saltarte el menú con flags:

```bash
python main.py --manifest
```

```bash
python main.py --test
```
