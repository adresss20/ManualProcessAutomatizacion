# Creador de Marcas — Farmacia a Domicilio

Sube en lote (~1,137 pendientes) las marcas/fabricantes del Excel al panel de
**farmaciasadomicilio.mx**, asociando cada marca a sus categorías, y marca en
verde en el Excel las que se van creando.

## Estructura

```
Creador de Marcas para Farmacias a domicilio/
├── input/
│   └── Marcas por crear.xlsx        ← fuente de datos (col B = marca, col C = categorías)
├── src/
│   ├── agregar_marcas.py            ← script principal (v2, corregido)
│   └── config_local.py              ← (opcional) tus credenciales; NO lo compartas
├── logs/
│   └── agregar_marcas.log           ← se genera al correr
├── docs/
│   ├── contexto_proyecto.md         ← endpoints/API del sitio (referencia)
│   └── agregar_marcas_ORIGINAL_v1.py← script anterior (histórico, con bugs)
├── requirements.txt
└── README.md
```

## Endpoints reales (verificados contra el sitio)

> El "contexto" del chat anterior tenía datos inventados. Estos son los reales:

| Paso | Método / URL | Notas |
|---|---|---|
| Página de login | `GET /user/login` | Campo `username` (acepta el correo), no `email` |
| Autenticación | `POST /user/loginViaUsername` | AJAX JSON; `data.is_email==1` = éxito. OTP solo aplica a login por teléfono |
| Token CSRF | `GET /client/category` | Dentro del `<form id="addBrandForm">` |
| Categorías (474) | `GET /client/brand/create` | Devuelve `{"success":true,"html":"..."}` con el `<select id="cateSelectBox">` |
| Marcas existentes | `GET /client/category` | Tabla `#brand-datatable` (para no duplicar) |
| **Crear marca** | `POST /client/brand` | multipart; `_token`, `language_id[]` (148=ES, 1=EN), `title[]`, `cate_id[]` |

Las 11 categorías top-level del sitio y sus IDs: Abarrotes y limpieza=2, Alimentos y
bebidas=6, Bebés=36, Cuidado personal y belleza=109, Dermocosméticos=194, Equipo y
botiquín=273, Mascotas=312, Medicamentos=315, Salud Natural=407, Salud sexual=444,
Vitaminas y suplementos=451. (El script las lee dinámicamente, no están hardcodeadas.)

## Cómo funciona

Es un script de **Python** (no un click-por-click en el navegador). Para 1,100+
marcas es la forma correcta: rápido, resumible y sin errores manuales.

1. Inicia sesión en el panel (Laravel, usa token CSRF).
2. Descarga del sitio la lista real de **categorías** (con sus IDs) y de **marcas ya existentes**.
3. Recorre el Excel fila por fila:
   - Omite las filas **ya verdes** (progreso resumible aunque se interrumpa).
   - Omite marcas que **ya existen** en el sitio (evita duplicados) y las pinta verde.
   - Mapea los nombres de categoría del Excel → IDs del sitio (acentos/mayúsculas + alias de typos + fuzzy).
   - `POST /client/brand` y **valida el éxito de verdad** (redirect + sin errores de validación).
   - Pinta la fila de verde y **guarda el Excel tras cada éxito**.
4. Al final registra las categorías que no pudo mapear, para revisarlas a mano.

## Uso

```bash
pip install -r requirements.txt
```

Credenciales del panel (NO van en el código). En PowerShell:

```powershell
$env:FAD_EMAIL="tu_correo@dominio.com"
$env:FAD_PASSWORD="tu_contraseña"
```

o crea `src/config_local.py` con `FAD_EMAIL = "..."` y `FAD_PASSWORD = "..."`.

Prueba primero (recomendado):

```bash
cd src
python agregar_marcas.py --dry-run --limit 10   # no toca el sitio; solo muestra el mapeo
python agregar_marcas.py --limit 5              # crea 5 reales para validar
```

Corrida completa:

```bash
python agregar_marcas.py
```

## Si el sitio pide un código OTP (login por cookie)

El login del panel (`/user/login`, campo `username`) puede pedir un **código OTP de
6 dígitos**. Si al correr ves el error *"El sitio pidió un código OTP"*, usa la sesión
de tu navegador en vez del login automático:

1. Inicia sesión normal en `https://farmaciasadomicilio.mx/user/login` en tu navegador.
2. Abre DevTools (F12) → pestaña **Application/Aplicación** → **Cookies** →
   `https://farmaciasadomicilio.mx`.
3. Copia el par `nombre=valor` de la cookie de sesión (Laravel suele llamarla
   `laravel_session`; copia esa, y si existe `XSRF-TOKEN` también, separadas por `;`).
4. Córrelo así (cmd), sin usar FAD_EMAIL/FAD_PASSWORD:

   ```bash
   set FAD_COOKIE=laravel_session=EL_VALOR_LARGO
   py src\agregar_marcas.py --limit 10
   ```

La cookie caduca a las pocas horas; si expira, vuelve a copiarla.

## Notas / decisiones

- **Verde = ya creada.** El script detecta cualquier relleno sólido en la columna B
  como "ya hecha". Unilever y P&G ya vienen en verde.
- **7 marcas ya existen en el sitio** (Unilever, P&G, Laboratorios PiSA, L'Oreal,
  Maver, Kimberly-Clark, Bayer). El script las detecta y las **salta** (las pinta
  verde sin recrearlas).
- **23 filas del Excel no tienen categoría** (columna C vacía). El script las **omite**
  y las cuenta como `errores/sin_cat` en el log (no inventa categorías). Revísalas a mano.
- **Mapeo de categorías: verificado, las 18 variantes del Excel resuelven a un ID real.**
  Decisión a confirmar: `Súper`, `Abarrotes`, `Super y abarrotes` y
  `Limpíeza y cuidado del hogar` se mapean a **Abarrotes y limpieza** (el sitio no tiene
  una categoría "Súper"). `Protector solar` → subcategoría id 145. Si prefieres otro
  destino para "Súper", edita `CATEGORY_ALIASES` en el script.
- El nombre en inglés se envía igual que en español (no hay columna separada).
