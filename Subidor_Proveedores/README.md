# Automatización de subida de proveedores (multi-MKP)

Da de alta proveedores (farmacias / vendors) en los marketplaces a partir de
`Información_Proveedores.xlsx`, repitiendo exactamente la carga manual, y **valida**
cada alta dejando el resultado en el mismo Excel.

Usa **Playwright** (un navegador Chrome real), porque la dirección depende del
autocompletado de Google Maps, que llena latitud, longitud, ciudad y estado.

## Flujo por proveedor (plataforma Farmacias a Domicilio / UNEFARM)

1. Proveedores → **Agregar**
2. Nombre, correo y teléfono
3. Dirección (plus code) → **clic en la sugerencia de Google** → espera a que se llenen latitud y longitud
4. Código postal (como texto, conserva el `0` inicial) y país
5. Descripción (si hay)
6. Detalles avanzados: **Disponibilidad 24/7** y **Tiempo de preparación** (el 0 es válido)
7. Activa **todas las categorías** con el mismo script que se pegaba con F12 ([src/js/activar_categorias.js](src/js/activar_categorias.js))
8. Guardar → **validador**: busca el proveedor en el listado y compara el plus code

## Instalación (una sola vez)

```bash
pip install -r requirements.txt
```

```bash
py -m playwright install chromium
```

Copia `.env.example` como `.env` y pon la URL, el usuario y la contraseña de cada MKP
(`MKP_<CLAVE>_URL / _USUARIO / _PASSWORD`). Si falta alguno, el programa lo pide por
consola. **No compartas el `.env`.**

## Uso

| Comando | Qué hace |
|---|---|
| `py src\main.py` | Menú para elegir el MKP y subir los pendientes |
| `py src\main.py --validar-excel` | Solo revisa los datos del Excel (sin navegador) |
| `py src\main.py --mkp FAD --diagnose` | **Primera vez**: revisa el formulario real **sin guardar nada** |
| `py src\main.py --mkp FAD --limit 2` | Prueba con 2 proveedores |
| `py src\main.py --mkp FAD` | Subida completa |
| `py src\main.py --mkp FAD --filas 10-20` | Solo esas filas del Excel |
| `py src\main.py --mkp FAD --verificar` | Solo confirma que cada proveedor esté en el panel |

Agrega `--headless` para que no se vea el navegador.

## Resultado en el Excel

Por cada MKP se agregan las columnas `Estado <MKP>`, `Observaciones <MKP>` y `Fecha <MKP>`,
y cada fila se colorea según el estado:

| Estado | Color | Significado |
|---|---|---|
| OK | verde | Se creó y aparece en el listado con la dirección correcta |
| REVISAR | amarillo | Se creó, pero hay algo que revisar (ver Observaciones) |
| YA EXISTE | azul | Ya estaba en el panel; no se duplicó |
| ERROR | rojo | No se pudo crear (motivo en Observaciones + captura en `logs/errores/`) |
| DATOS INVALIDOS | rojo | El Excel tiene un dato mal (correo, teléfono, CP, etc.) |
| NO ENCONTRADO | rojo | (`--verificar`) no aparece en el panel |

- Se puede **volver a correr** sin riesgo: las filas OK, REVISAR y YA EXISTE se saltan, y antes de crear
  un proveedor se comprueba que no exista ya. Las filas en ERROR o con datos inválidos se reintentan.
- Se pueden agregar o quitar filas libremente; las filas vacías se ignoran.
- Antes de cada corrida se guarda un respaldo del Excel en `output/backups/`.
- Si el Excel está abierto, los resultados se escriben en `output/<nombre>_resultado_<MKP>.xlsx`.

## Agregar otro marketplace

- **Mismo software (panel /client)**: añade una entrada en `MARKETPLACES` de
  [src/config.py](src/config.py) con `"plataforma": "fad"` y sus credenciales en `.env`.
- **Otro software**: crea `src/plataformas/<nuevo>.py` heredando de `Plataforma`
  ([base.py](src/plataformas/base.py)), con los métodos `login`, `buscar`, `alta` y `diagnosticar`,
  y regístralo en [src/plataformas/__init__.py](src/plataformas/__init__.py).

## Estructura

```
Automatización_subida_Proveedores/
├── Información_Proveedores.xlsx   ← fuente de datos + resultados
├── .env / .env.example            ← URL/usuario/contraseña por MKP
├── src/
│   ├── main.py                    ← CLI, menú de MKP, flujo y validador
│   ├── config.py                  ← registro de MKP, tiempos, colores
│   ├── entorno.py                 ← .env y credenciales
│   ├── excel_io.py                ← lectura, validación y marcado del Excel
│   ├── js/activar_categorias.js   ← script de categorías (F12)
│   └── plataformas/fad.py         ← automatización del panel FAD/UNEFARM
├── output/backups/
└── logs/                          ← log de cada corrida, diag_<MKP>/, errores/
```

## Notas

- Los campos se ubican por el **texto de su etiqueta** ("Correo electrónico", "Latitud"…), no por IDs internos.
  Si el panel cambia y algo falla, `--diagnose` dice qué campo no encuentra y guarda el HTML en `logs/diag_<MKP>/`.
- UNEFARM está registrado con la misma plataforma que FAD, pero todavía no se ha probado su formulario de alta.
