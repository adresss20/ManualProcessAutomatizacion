# Subidor de inventarios (multi-MKP)

Importa el **CSV de inventario** de cada proveedor en el marketplace, según
`Enlaces por nombre.xlsx`:

| Columna | Contenido |
|---|---|
| `Nombre_proveedor` | Proveedor a buscar en el MKP (coincidencia **exacta**) |
| `Name_inventario` | Archivo CSV dentro de `Inventarios\` |

Hace por HTTP lo mismo que el proceso manual (Proveedores → buscar → perfil → **Importar**
→ "Agregar servicio" → elegir CSV), sin abrir navegador.

## Flujo por fila

1. **Valida el CSV antes de subirlo.** Lo ubica en `Inventarios\` (tolera puntos o `.csv`
   sobrantes), revisa que tenga UTF-8 y las columnas SKU/Title, y **bloquea SKU en notación
   científica** (`7.50135E+12`).
2. Busca el proveedor por **nombre exacto** en las 3 pestañas. Si no lo encuentra → NO ENCONTRADO,
   y en Observaciones lista los parecidos. Si hay 2 con el mismo nombre → ERROR.
3. Sube el CSV a `POST /client/product/importCSV` con los campos del formulario del panel.
4. **Validador:** espera hasta `--espera` segundos (90 por defecto) a que el archivo aparezca
   en el historial de importaciones del proveedor y termine. Anota el estado del panel y
   **Total Servicios antes → después**.

## Instalación

```bash
pip install -r requirements.txt
```

Copia el `.env` del Creador de cobertura (mismo formato `MKP_<CLAVE>_URL/_USUARIO/_PASSWORD`).

## Uso

| Comando | Qué hace |
|---|---|
| `py src\main.py --validar` | Revisa el Excel y los CSV sin conectarse |
| `py src\main.py --convertir Inventario_tiendas.xlsx` | Genera `Inventarios\Inventario_tiendas.csv` desde el .xlsx con los **SKU completos** |
| `py src\main.py --mkp FAD --diagnose` | **Primera vez**: revisa el formulario de importación **sin subir nada** |
| `py src\main.py --mkp FAD --limit 2` | Prueba con 2 |
| `py src\main.py` | Menú para elegir el MKP y subir los pendientes |
| `py src\main.py --mkp FAD --verificar` | Confirma en el panel las filas que quedaron EN PROCESO |

`--forzar` sube aunque el CSV tenga errores. No se recomienda.

## Por qué existe `--convertir`

Al guardar como CSV, Excel convierte los códigos de barras en notación científica:
`7501349012004` pasa a `7.50135E+12`. En el CSV original, **5,974 de 6,173 SKU** estaban así y
solo quedaban **603 SKU distintos**: el panel habría juntado miles de productos distintos.
`--convertir` lee los valores reales del `.xlsx` y escribe el CSV en UTF-8, con los SKU como texto.

## Resultado en el Excel

| Estado | Color | Significado |
|---|---|---|
| OK | verde | El panel procesó el archivo con éxito |
| EN PROCESO | amarillo | Se subió; el panel lo sigue procesando → `--verificar` más tarde |
| NO ENCONTRADO | rojo | No hay proveedor con ese nombre exacto (Observaciones lista parecidos) |
| ERROR | rojo | El panel rechazó o falló la importación (con enlace al detalle si existe) |
| DATOS INVALIDOS | rojo | El CSV no existe o no es apto, o falta información en la fila |

Las filas OK y EN PROCESO no se vuelven a subir. Antes de cada corrida se guarda un respaldo
en `output\backups\`.

## Estructura

```
src/
├── main.py            CLI, flujo y validador
├── config.py          MKP, tiempos de espera, estados y colores
├── entorno.py         .env y credenciales
├── excel_io.py        Enlaces por nombre.xlsx
├── inventario.py      ubicar / validar / convertir CSV
└── mkp/cliente_fad.py cliente HTTP del panel (login, proveedores, importación), reutilizable
```
