# Sitemap Completo — farmaciasadomicilio.mx/client/
**Panel de administración de farmacia quick-commerce**
**Generado:** Septiembre 2026 | **Levantado en vivo** desde farmaciasadomicilio.mx

---

## 1. CONTEXTO GENERAL DE LA APLICACIÓN

**URL base del panel:** `https://farmaciasadomicilio.mx/client/`

**Tipo de aplicación:** Single Page Application (SPA) — probablemente Vue.js con backend Laravel. Esto significa que:
- **La navegación directa por URL rompe la app** y muestra un error "Boo! You don't have an internet connection"
- Se debe navegar SIEMPRE desde el dashboard (`/client/dashboard`) haciendo clic en el sidebar, o usando patrones de URL probados como `/client/product/{id}/edit` y `/client/vendor/catalogs/{id}`
- Las rutas del SPA cambian la URL en el navegador sin hacer recarga de página

**Plataforma base:** Parece basarse en Stackfood / 6amMart o plataforma similar de quick-commerce multi-vendedor adaptada para farmacias.

**Concepto de negocio:** Marketplace de entrega de medicamentos y productos farmacéuticos a domicilio. Las "farmacias" son los "proveedores/vendedores" (vendors). Los "medicamentos/productos" son los "servicios".

**Header superior (barra fija):**
- Logo: ícono de manos con corazón + texto "Farmaciasadomicilio.mx"
- "Ver sitio web" → abre el sitio público para clientes
- "Idioma es" → selector de idioma
- Toggle oscuro/claro → cambio de tema
- Ícono de usuario → perfil del administrador

---

## 2. ESTRUCTURA DEL SIDEBAR (Menú lateral izquierdo)

El sidebar tiene 3 secciones principales:

```
SOLICITUDES
CONFIGURACIÓN
MARKETING
```

_(Más herramientas adicionales al fondo)_

---

## 3. SECCIÓN: SOLICITUDES (Operaciones)

### 3.1 Panel principal
- **Ruta:** `/client/dashboard`
- **Función:** KPIs globales del período seleccionado
- **Contenido:**
  - Tarjeta "Solicitudes": número total de órdenes + % de cambio vs. mes anterior
  - Tarjeta "Servicios": número de servicios + % de cambio vs. mes anterior
  - Selector de rango de fechas (esquina superior derecha)
- **Notas:** El dashboard es el punto de entrada. Sin él cargado, el resto del SPA no funciona correctamente.

---

### 3.2 Solicitudes (Orders)
- **Función:** Gestión completa de órdenes/pedidos
- **Pestañas dentro de la página:**
  1. **Pendientes** — Órdenes esperando aceptación
  2. **Activos** — Órdenes en proceso de preparación/entrega
  3. **Historial** — Órdenes completadas
  4. **Solicitud de devolución** — Devoluciones solicitadas por clientes
  5. **Cancelación** — Órdenes canceladas
- **Información visible por orden:** artículos, precios, datos del paciente, dirección de entrega, farmacia asignada, repartidor, estado

---

### 3.3 Proveedores (Farmacias / Vendors)
- **Ruta:** `/client/vendor/catalogs`
- **Función:** Gestión de todas las farmacias registradas en la plataforma
- **Vista de lista:** Muestra todas las farmacias activas con su info básica

#### 3.3.1 Perfil de proveedor individual
- **Ruta:** `/client/vendor/catalogs/{id}`
- **Panel izquierdo:**
  - Foto de perfil de la farmacia
  - Nombre de la farmacia (ej. "Farmacia Morelia III")
  - Dirección completa (calle, colonia, ciudad, estado, país)
  - Botón **Editar** → editar datos del perfil
  - Botón **Block** → bloquear/desbloquear proveedor
  - Botón **"Gestionar URLs de redes sociales"** → enlaces sociales

- **Pestañas principales (panel derecho):**

##### TAB 1: Catálogo
- **Función:** Ver y gestionar todos los productos/medicamentos de esta farmacia
- **Estadísticas en la parte superior:**
  - Total Servicios (total de productos en catálogo)
  - Publicado Servicios (visibles para el cliente)
  - Entregables a domicilio
  - Nuevo Servicios (marcados como nuevos)
  - Destacado Servicios (productos destacados)

- **Tabla de catálogo:**
  - Columnas: checkbox, posición (↕), #, Nombre del producto, Categoría, Marca, Cantidad (stock), Producto alquilado, Precio
  - Filtro de búsqueda por nombre
  - Dropdown "Seleccionar" para filtros adicionales

- **Acciones disponibles (botones superiores):**
  - **Importar** → importar catálogo desde archivo
  - **Exportar como PDF** → generar PDF del catálogo
  - **Exportar** → exportar en formato de datos
  - **Agregar servicio** → agregar nuevo producto manualmente

- **Por cada fila de producto:**
  - Botón azul "+" → agregar/editar
  - Ícono de edición → ir a editar el producto

##### TAB 2: Configuración (del proveedor)
- **Función:** Ajustes operativos específicos de esta farmacia

| Campo | Tipo | Descripción |
|---|---|---|
| Tiempo de preparación (minutos) | Número | Cuánto tarda en preparar pedidos |
| Destacado | Toggle | Destacar esta farmacia en el marketplace |
| Disponibilidad 24/7 | Toggle | Si opera 24 horas |
| Duración del horario (minutos) | Dropdown | Duración de cada franja horaria |
| Pedidos máximos por horario | Número | Límite de pedidos por franja |
| Fixed Fee Per Order | Toggle | Cargo fijo por pedido |
| Ocultar desglose de precio | Toggle + ℹ️ | Ocultar desglose al cliente |
| Aceptación automática de solicitudes | Toggle | Auto-aceptar pedidos |
| ¿Necesitas cargos por contenedor? | Toggle | Cargos adicionales por empaque |
| Solicitud de devolución | Toggle | Permitir devoluciones |
| Cancelar pedido en proceso | Toggle | Permitir cancelar pedidos activos |

_(Puede haber más campos debajo del scroll)_

##### TAB 3: Categorías y complementos
- **Función:** Gestión de categorías específicas de esta farmacia y sus productos complementarios/add-ons

---

### 3.3.2 ⭐ Editar Servicio/Producto (CAMPO DE RECETA)
- **Ruta:** `/client/product/{id}/edit`
- **Acceso:** Desde Catálogo del proveedor → clic en un producto → editar
- **Función:** Edición completa de un medicamento/producto

**Campos generales del producto:**
- Nombre del producto
- Descripción
- Precio
- Cantidad/stock
- Categoría
- Marca
- Imágenes del producto
- Toggle: Entregable a domicilio
- Toggle: Nuevo (marca el producto como "nuevo")
- Toggle: Destacado (featured)
- Toggle: Publicado/visible

**🔑 SECCIÓN: INFORMACIÓN ADICIONAL (campos de receta)**

> Esta es la ÚNICA sección en toda la aplicación con controles de receta electrónica.

| Campo | Tipo | Función |
|---|---|---|
| **Requiere prescripción médica** | Toggle ON/OFF | Indica que este medicamento requiere receta para ser adquirido |
| **Validar receta** | Toggle ON/OFF | Activa el flujo de validación/verificación de la receta presentada |

**Notas críticas:**
- ❌ **NO existe configuración global de receta** en ninguna otra parte del panel
- Cada producto debe configurarse **individualmente**
- Si un medicamento requiere receta, se deben activar los dos toggles en su página de edición
- La ruta es siempre `/client/product/{id}/edit` donde `{id}` es el ID numérico del producto
- Para configurar receta en toda una farmacia, se debe entrar producto por producto

---

### 3.4 Contabilidad
- **Función:** Reportes financieros y gestión de pagos
- **Sub-secciones:**
  1. **Vendors Payment Report** — Reporte de pagos a farmacias
  2. **Solicitudes** — Solicitudes financieras
  3. **Tarjetas de fidelidad** — Gestión de loyalty cards
  4. **Códigos promocionales** — Reportes de uso de códigos promo
  5. **Impuestos** — Reportes de impuestos generados
  6. **Proveedores** — Pagos y cuentas por proveedor
  7. **Solicitudes de retiro** — Solicitudes de retiro de fondos de farmacias

---

### 3.5 Pacientes
- **Función:** Gestión de la base de usuarios/clientes (pacientes)
- **Vista:** Lista de todos los pacientes registrados
- **Filtros:** Activo / Inactivo
- **Datos por paciente:** nombre, contacto, estado de cuenta

---

### 3.6 Informes (Reports)
- **Sub-secciones:**
  1. **Reseñas de Servicios** — Reviews y calificaciones que clientes dejan sobre los productos
  2. **Informe de rendimiento de Servicios** — Métricas de desempeño de productos/servicios

---

### 3.7 Área de servicio del administrador
- **Función:** Gestión de zonas de cobertura geográfica
- **Contenido:** Configuración de polígonos/zonas donde opera la plataforma, radios de entrega, áreas disponibles

---

## 4. SECCIÓN: CONFIGURACIÓN (Settings)

### 4.1 Perfil
- Datos del administrador del panel
- Cambio de foto, nombre, contraseña

---

### 4.2 Personalizar (Localización)
- **Función:** Configuración regional de la plataforma
- **Campos:**
  - Formato de fecha
  - Formato de hora
  - Moneda (currency)
  - Idiomas disponibles en la app

---

### 4.3 Estilo
- **Función:** Apariencia visual y branding de la plataforma
- Tiene sub-secciones (indicado con ">")
- Colores, fuentes, logos, modo claro/oscuro por defecto

---

### 4.4 CMS (Content Management System)
- Tiene sub-secciones:

| Sub-sección | Función |
|---|---|
| **Páginas** | Gestión de páginas estáticas (Términos, Política de privacidad, FAQ, etc.) |
| **Correos electrónicos** | Plantillas de emails transaccionales (confirmación de pedido, etc.) |
| **Notificaciones** | Plantillas de notificaciones push |
| **SMS** | Plantillas de mensajes SMS |
| **Motivos** | Razones predefinidas para cancelaciones, devoluciones, quejas |

**Nota:** No hay templates específicos de receta electrónica en ninguna de estas secciones.

---

### 4.5 Catálogo (Global)
- **Función:** Categorías y variantes a nivel global (aplica a todos los proveedores)
- **Sub-secciones:**
  - **Categorías** — Árbol de categorías de productos (ej. Parches, Probióticos, Faciales, Corporales, Suplementos y complementos)
  - **Variantes** — Configuración de variantes de productos (tamaños, presentaciones, etc.)

---

### 4.6 Configuraciones
- **Ruta:** `/client/configure`
- **Función:** Configuración técnica global de la plataforma
- **NO contiene ajustes de receta electrónica**

| Tab/Sección | Función |
|---|---|
| **Hiperlocal** | Configuración de lógica de búsqueda y entrega basada en ubicación precisa |
| **Entrega** | Parámetros de entrega: distancias, tiempos, tarifas base |
| **Pagos** | Métodos de pago habilitados, pasarelas de pago |
| **Social** | Integración con redes sociales (login social, etc.) |
| **SMS** | Configuración de gateway SMS (proveedor, API keys) |
| **Correo** | Configuración de servidor de email (SMTP, API) |
| **Firebase** | Integración Firebase para notificaciones push |
| **Soporte** | Configuración de chat de soporte o helpdesk |
| **CRM** | Integración con sistema CRM |
| **P2P** | Configuración Peer-to-Peer (posiblemente entrega peer-to-peer) |
| **Inventario** | Configuración de gestión de inventario |

---

### 4.7 Impuesto
- **Función:** Configuración de tasas de impuesto aplicables a productos/entregas

---

### 4.8 Opciones de pago
- **Función:** Configuración de métodos de pago disponibles para los clientes (tarjeta, efectivo, transferencia, etc.)

---

### 4.9 Gestionar entrega
- **Función:** Gestión de repartidores, zonas, tarifas
- Tiene sub-secciones (indicado con ">")

---

### 4.10 Gestionar roles
- **Función:** Control de acceso basado en roles
- Crear/editar roles con diferentes permisos sobre el panel

---

### 4.11 Control de caché
- **Función:** Limpieza y gestión del caché del sistema
- Útil para reflejar cambios inmediatos en la plataforma pública

---

## 5. SECCIÓN: MARKETING

### 5.1 Banners
- **Función:** Gestión de imágenes/banners promocionales en la app del cliente
- Tiene sub-secciones (posiblemente por tipo: banner principal, banner secundario, etc.)

---

### 5.2 Código promocional
- **Función:** Creación y gestión de códigos de descuento
- CRUD completo de cupones: monto, %, condiciones, vigencia, uso máximo

---

### 5.3 Tarjetas de fidelidad
- **Función:** Programa de lealtad / loyalty cards para clientes frecuentes
- Configuración de puntos, canjes, beneficios

---

### 5.4 Campañas
- **Función:** Gestión de campañas de marketing
- Posiblemente push campaigns, email campaigns, SMS masivos

---

## 6. SECCIÓN: HERRAMIENTAS (Extra)

### 6.1 Herramientas
- **Sub-herramientas:**
  1. **Copia de catálogo** — Clonar el catálogo de un proveedor a otro
  2. **Copia de impuestos** — Copiar configuración de impuestos entre proveedores
  3. **Subir múltiples archivos** — Carga masiva de imágenes u otros archivos
  4. **Restablecer configuración** — Reset de ajustes a valores por defecto

---

### 6.2 Registros de auditoría de BD
- **Función:** Logs de actividad sobre la base de datos
- Útil para auditoría de cambios, debugging, seguridad

---

## 7. MAPA DE RECETA ELECTRÓNICA (RESUMEN CRÍTICO)

### 7.1 ¿Dónde está?

```
SOLICITUDES
  └── Proveedores
        └── [seleccionar farmacia] → Catálogo
              └── [clic en un producto] → Editar Servicio
                    └── INFORMACIÓN ADICIONAL
                          ├── 🔘 Requiere prescripción médica  ← CAMPO 1
                          └── 🔘 Validar receta                ← CAMPO 2
```

**URL directa:** `https://farmaciasadomicilio.mx/client/product/{id}/edit`

### 7.2 ¿Qué hace cada campo?

| Campo | ON | OFF |
|---|---|---|
| Requiere prescripción médica | El producto exige que el cliente tenga receta | Sin requerimiento de receta |
| Validar receta | Se activa un flujo de validación/verificación de la receta presentada | No se valida receta |

### 7.3 Lo que NO existe

- ❌ No hay "Configuración global de receta" en `/client/configure`
- ❌ No hay toggle de receta a nivel de proveedor/farmacia
- ❌ No hay templates de CMS específicos de receta
- ❌ No hay sección de "Receta electrónica" o "Receta sencilla" en ningún menú del sidebar
- ❌ No hay reporte de recetas en la sección de Informes

### 7.4 Implicaciones operativas

Para habilitar receta en toda la plataforma o para un proveedor específico, se debe:
1. Ir a **Proveedores** → seleccionar la farmacia
2. En el **Catálogo**, identificar cada medicamento que requiere receta
3. Entrar al **Editar Servicio** de cada producto individualmente
4. En **INFORMACIÓN ADICIONAL**, activar los toggles correspondientes
5. Repetir por cada producto (no hay operación masiva visible)

---

## 8. NOTAS TÉCNICAS IMPORTANTES

### 8.1 Navegación SPA
- La app es un SPA. Hacer `navigate()` a una URL interna directamente rompe el estado.
- Siempre cargar `/client/dashboard` primero y luego navegar por clics, O
- Usar URLs que el SPA soporta como punto de entrada: `/client/vendor/catalogs/{id}`, `/client/product/{id}/edit`

### 8.2 IDs conocidos
- Vendor ID 7 = **Farmacia Morelia III** (Calle Poniente 1 19, Cuchilla del Tesoro, CDMX)
- Products tienen IDs numéricos (ej. `/client/product/483/edit`)

### 8.3 Estructura del catálogo de productos (columnas visibles)
- Nombre del producto
- Categoría (ej: Parches y telas adhesivas, Corporales, Faciales, Probióticos y Prebióticos, Suplementos y complementos)
- Marca (ej: 3M, Nexcare, BioGaia, N/A)
- Cantidad (stock disponible)
- Producto alquilado (boolean)
- Precio (en MXN)

### 8.4 Categorías de productos observadas
- Parches y telas adhesivas
- Corporales
- Faciales
- Probióticos y Prebióticos
- Suplementos y complementos

---

## 9. URL PATTERNS CONFIRMADOS

| Sección | URL | Notas |
|---|---|---|
| Dashboard | `/client/dashboard` | Punto de entrada; siempre cargar aquí primero |
| Lista de proveedores | `/client/vendor/catalogs` | Funciona como SPA route |
| Perfil de proveedor | `/client/vendor/catalogs/{id}` | `{id}` = número entero |
| Editar producto | `/client/product/{id}/edit` | **Aquí están los campos de receta** |
| Configuraciones globales | `/client/configure` | Sin ajustes de receta |

---

*Documento generado a partir de exploración en vivo del panel de administración de farmaciasadomicilio.mx en septiembre de 2026. Válido para la versión del panel observada en esa fecha.*
