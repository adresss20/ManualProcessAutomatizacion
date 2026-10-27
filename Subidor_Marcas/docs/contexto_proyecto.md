# Farmacia a Domicilio — Contexto del Proyecto de Automatización de Marcas

## Objetivo
Agregar ~1,000 marcas al panel de administración de **farmaciasadomicilio.mx** de forma automatizada, leyendo los datos de un Excel local y marcando en verde las filas ya procesadas.

---

## Lo que ya se hizo

- Se exploró el sitio manualmente con Claude en Chrome
- Se identificó el endpoint y la estructura del formulario para agregar marcas
- Se agregó "Unilever" de prueba — **ya existe en la base de datos del sitio**
- Se construyó el script Python `agregar_marcas.py` (listo para configurar y correr)

---

## Endpoints y estructura del sitio

### Base URL
```
https://farmaciasadomicilio.mx
```

### Login
| Campo | Valor |
|---|---|
| URL | `https://farmaciasadomicilio.mx/client/login` |
| Método | `GET` (para obtener CSRF) → `POST` (para autenticar) |
| Campos POST | `_token`, `email`, `password` |
| CSRF tag | `<input name="_token">` en el HTML de la página |

### Página de categorías y marcas
```
GET https://farmaciasadomicilio.mx/client/category
```
- Contiene el `_token` CSRF fresco
- Contiene el `<select id="cateSelectBox">` con todas las categorías y sus IDs numéricos
- Es la página de referencia para refrescar el CSRF antes de cada POST

### Agregar marca ⭐ Endpoint principal
```
POST https://farmaciasadomicilio.mx/client/brand
```

**Campos del formulario (multipart/form-data o urlencoded):**

| Campo | Tipo | Descripción |
|---|---|---|
| `_token` | string | CSRF token, obtenido del HTML de `/client/category` |
| `language_id[]` | string | `"148"` = Español |
| `title[]` | string | Nombre de la marca en Español |
| `language_id[]` | string | `"1"` = Inglés |
| `title[]` | string | Nombre de la marca en Inglés |
| `cate_id[]` | string (repetido) | ID numérico de cada categoría (puede repetirse N veces) |
| `image1` | file (opcional) | Logotipo 350×200 |
| `image2` | file (opcional) | Banner 1920×1080 |

> **Importante:** `language_id[]` y `title[]` son pares ordenados. El primer `language_id[]` corresponde al primer `title[]`, y así sucesivamente. En Python con `requests` se envían como lista de tuplas:
> ```python
> data = [
>     ("_token", csrf_token),
>     ("language_id[]", "148"),
>     ("title[]", "Unilever"),   # español
>     ("language_id[]", "1"),
>     ("title[]", "Unilever"),   # inglés
>     ("cate_id[]", "6"),        # Alimentos y bebidas
>     ("cate_id[]", "36"),       # Bebés
> ]
> session.post("https://farmaciasadomicilio.mx/client/brand", data=data)
> ```

**Respuesta esperada al éxito:** Redirect 302 a `/client/category`

---

## Categorías del sitio (IDs numéricos)

El sitio usa el plugin **Selectize.js** en `<select id="cateSelectBox">`.
Las categorías con `>` al inicio son subcategorías.

```
ID   Nombre
──   ─────────────────────────────────────────────
2    Abarrotes y limpieza
3      > Despensa
4      > Abarrotes
5      > Cigarrillos
6    Alimentos y bebidas
7      > Alimentos sin azucar
8      > Cereales, galletas y granolas
9      > Dulces y chocolates
10     > Otros alimentos sin azúcar
11     > Suplementos alimenticios
12     > Sustitutos de azúcar
13     > Bebidas
14     > Aguas purificadas
15     > Aguas saborizadas
16     > Bebidas isotónicas
17     > Refrescos
18     > Jugos y néctares
19     > Botanas
20     > Frutos
21     > Palomitas
22     > Snacks
23     > Café y chocolate en polvo
24     > Café soluble
25     > Chocolates en polvo
26     > Cereales, galletas y dulces
27     > Cereales
28     > Chocolates
29     > Dulces
30     > Galletas
31     > Mieles untables
32     > Leche líquida y en polvo
33     > Bebidas vegetales
34     > Leches en polvo
35     > Leches líquidas
36   Bebés
37     > Accesorios para bebé
38     > Cuidado de bebés y niños
39     > Aspiradores nasales
40     > Biberones y accesorios
41     > Chupones
42     > Higiene y cuidado
43     > Kit médico
44     > Mordederas
45     > Protectores de pezones
46     > Tetinas
47     > Utensilios para bebé
48     > Vasos entrenadores
49     > Alimentos para bebés
50     > Cereal
51     > Accesorios de alimentación
52     > Aguas para bebés
53     > Alimentos orgánicos para bebé
54     > Jugos
55     > Leche en polvo
56     > Papillas
57     > Yogurts
58     > Cuidados del bebé
59     > Toallitas húmedas
60     > Aceites
61     > Aplicadores
62     > Cremas de bebé
63     > Cuidado dental del bebé
64     > Pomadas y ungüentos
65     > Shampoos y jabones
66     > Talcos
67     > Dermopediatría
68     > Cremas para bebé
69     > Cremas para sol
70     > Especiales para mamás
71     > Geles y jabones
72     > Lociones y aguas de tocador
73     > Repelente de mosquitos
74     > Shampoos para bebé
75     > Talcos y aceites
76     > Toallitas húmedas bebé
77     > Fórmulas infantiles
78     > Alimento para mamá
79     > Especializadas
80     > Regulares-etapa 1
81     > Regulares-etapa 2
82     > Regulares-etapa 3
83     > Regulares-etapa 4
84     > Lactancia
85     > Bolsas para leche materna
86     > Extractores de leche
87     > Protectores de lactancia
88     > Protectores de pezón
89     > Maternidad
90     > Cuidado de la piel
91     > Pañales
92     > Niña-etapa 3
93     > Niña-etapa 4
94     > Niña-etapa 5
95     > Niña-etapa 6
96     > Niño-etapa 3
97     > Niño-etapa 4
98     > Niño-etapa 5
99     > Niño-etapa 6
100    > Unisex-etapa 1
101    > Unisex-etapa 2
[474 categorías en total — el script las obtiene dinámicamente de la página]
```

> El script Python obtiene **todas** las categorías automáticamente haciendo GET a `/client/category` y parseando el select, por lo que no necesitas copiarlas manualmente.

---

## Tecnología del sitio

| Tecnología | Detalle |
|---|---|
| Backend | Laravel (PHP) — usa `_token` CSRF en cada POST |
| Auth | Sesión Laravel (`laravel_session` cookie) |
| Frontend | jQuery 3.1.1, Axios, Selectize.js, Bootstrap |
| Categorías | Selectize en `<select id="cateSelectBox" name="cate_id[]">` |
| Idiomas | 148 = Español, 1 = Inglés |

---

## El script Python (`agregar_marcas.py`)

Ya está construido. Solo falta configurar:

### 1. Qué configurar en la sección CONFIG

```python
EMAIL    = "TU_EMAIL@ejemplo.com"       # credenciales del panel
PASSWORD = "TU_CONTRASEÑA"

EXCEL_PATH = r"C:\ruta\a\tu\archivo.xlsx"

# Modo de categorías en el Excel:
CATEGORY_MODE = "multi_column"  # o "single_cell"

# Si es multi_column: qué índice de columna corresponde a qué categoría
CATEGORY_COLUMNS = {
    3: "Cuidado personal y belleza",
    4: "Dermocosméticos",
    # ... etc
}

# Si es single_cell: columna que tiene todas las categorías separadas por comas
COL_CATEGORIES = 2
```

### 2. Información pendiente del Excel (necesaria para terminar de configurar)

- ¿Cuántas columnas tiene? ¿Cuál es la columna del fabricante (A, B…)?
- ¿Cómo están las categorías? ¿Una columna por categoría con "X", o todas en una celda?
- ¿Las categorías en el Excel usan los mismos nombres que el sitio?
- ¿Hay columna separada para el nombre en inglés o es el mismo?

### 3. Cómo correrlo

```bash
pip install requests openpyxl beautifulsoup4 rapidfuzz
python agregar_marcas.py
```

---

## Comportamiento del script

- ✅ Omite filas ya verdes (progreso guardado aunque el script se detenga)
- ✅ Fuzzy matching de categorías (tolerante a diferencias de mayúsculas/acentos)
- ✅ Guarda el Excel tras cada marca exitosa
- ✅ Refresca CSRF cada 50 marcas
- ✅ Log en consola y en `agregar_marcas.log`
- ✅ 1 segundo de espera entre peticiones para no saturar el servidor

---

## Próximos pasos

1. Compartir estructura del Excel (columnas, nombres de categorías)
2. Ajustar `CATEGORY_COLUMNS` en el script con los índices correctos
3. Correr en modo prueba con 5–10 filas para validar el mapeo de categorías
4. Correr completo para las ~1,000 marcas restantes
