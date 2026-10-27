"""
Plataforma "fad": panel /client de Farmacias a Domicilio (y UNEFARM, mismo software).

Reproduce la carga manual:
  Proveedores → Agregar → Nombre, Correo, Teléfono, Dirección (plus code + clic en la
  sugerencia de Google para autollenar lat/long/ciudad/estado), CP, País, Descripción,
  Disponibilidad 24/7, Tiempo de preparación → activar todas las categorías (JS) → Guardar.

Los campos se localizan por el TEXTO de su etiqueta (no por ids internos), así que
sobreviven a cambios menores del HTML. Si algo no se encuentra, correr --diagnose.
"""
import re
import time
from pathlib import Path
from urllib.parse import parse_qs

from playwright.sync_api import Error as PWError
from playwright.sync_api import TimeoutError as PWTimeout

from config import DELAY_TECLEO, ERRORES_DIR, TIMEOUT_AUTOCOMPLETE, TIMEOUT_GUARDAR
from excel_io import norm, plus_code
from .base import ErrorAlta, Plataforma, ProveedorEnSitio, ResultadoAlta

JS_CATEGORIAS = (Path(__file__).resolve().parent.parent / "js" / "activar_categorias.js").read_text(encoding="utf-8")

# Etiquetas tal como aparecen en el modal "Agregar vendors".
ET_NOMBRE = "Nombre"
ET_CORREO = "Correo electrónico"
ET_TELEFONO = "Número de teléfono"
ET_DIRECCION = "Dirección"
ET_CP = "Código postal"
ET_LAT = "Latitud"
ET_LNG = "Longitud"
ET_CIUDAD = "Ciudad"
ET_ESTADO = "Estado / Provincia"
ET_PAIS = "País"
ET_DESCRIPCION = "Descripción"
ET_24_7 = "Disponibilidad 24/7"
ET_PREPARACION = "preparación"          # "Tiempo de preparación (minutos)"

INPUT_VISIBLE = "input[not(@type='hidden') and not(@type='checkbox') and not(@type='radio') and not(@type='file')]"
ETIQUETAS_XP = "self::label or self::span or self::p or self::h5 or self::h6 or self::strong or self::div"

RE_BOTON_GUARDAR = re.compile(r"guardar|enviar|save|submit|crear|agregar|añadir|registrar", re.I)
RE_BOTON_EXCLUIR = re.compile(r"usuario|user|cancel|cerrar|close", re.I)

JS_ERRORES = r"""
() => {
  const sel = '.invalid-feedback, .text-danger, label.error, span.error, .help-block, .alert-danger,'
            + ' .parsley-errors-list li, .toast-error, .toast-message, .swal2-html-container, .swal2-title,'
            + ' .iziToast-message, .noty_body';
  return Array.from(document.querySelectorAll(sel))
    .filter(e => e.offsetParent !== null && e.innerText.trim())
    .map(e => e.innerText.trim().replace(/\s+/g, ' '))
    .filter(t => !/^Tama[nñ]o (del|de)/i.test(t))
    .slice(0, 8);
}
"""

JS_TOGGLE = r"""
(el, quiero) => {
  if (el.checked !== quiero) {
    const lab = el.closest('label') || (el.id && document.querySelector(`label[for="${el.id}"]`)) || el.nextElementSibling;
    (lab || el).click();
    if (el.checked !== quiero) el.click();
  }
  return el.checked;
}
"""

JS_FILAS = r"""
(tabla) => Array.from(document.querySelectorAll(`${tabla || 'table'} tbody tr`))
  .map(tr => Array.from(tr.querySelectorAll('td')).map(td => td.innerText.trim()))
"""


def _xp_etiqueta(texto: str, exacto: bool) -> str:
    cond = f"normalize-space(text())='{texto}'" if exacto else f"contains(normalize-space(text()),'{texto}')"
    return f".//*[{ETIQUETAS_XP}][{cond}]"


def _archivo_seguro(s: str) -> str:
    return re.sub(r"[^\w\-]+", "_", s)[:60]


class PlataformaFAD(Plataforma):
    LOGIN_PATH = "/user/login"
    VENDOR_PATH = "/client/vendor"
    DASHBOARD_PATH = "/client/dashboard"

    # ══════════════════════════════════════════
    #  Navegación
    # ══════════════════════════════════════════
    def login(self, usuario: str, password: str) -> None:
        # Los errores de Playwright incluyen el texto escrito con fill(); se
        # capturan aquí para que la contraseña nunca salga en consola ni en logs.
        try:
            self._login(usuario, password)
        except PWError as e:
            self._captura("login_fallido")
            self._volcar_html("login_fallido")
            detalle = str(e).split("\n")[0].replace(password, "****")
            raise SystemExit(f"No se pudo iniciar sesión: {detalle}\n"
                             "Captura y HTML en logs/errores/login_fallido.*") from None

    def _login(self, usuario: str, password: str) -> None:
        p = self.page
        p.goto(self.base_url + self.LOGIN_PATH, wait_until="load")
        self._esperar_red(8_000)
        # Formulario #login-form-new: correo → Continuar → el sitio valida el correo
        # (/user/check-valid-email) y recién ahí muestra #password-wrapper.
        form = p.locator("#login-form-new")
        if not form.count():
            form = p.locator("form:has(input[type='password'])").first
        campo_usuario = form.locator("input[name='username'], input[type='email']").first
        campo_usuario.wait_for(state="visible")
        campo_usuario.fill(usuario)
        continuar = form.locator(".login_continue_btn, button[type='submit']").first
        campo_pass = form.locator("input[type='password']").first
        error_msg = p.locator("#error-msg:visible").first

        if not campo_pass.is_visible():
            continuar.click()
            fin = time.time() + 20
            while time.time() < fin and not campo_pass.is_visible():
                if error_msg.count() and error_msg.inner_text().strip():
                    raise PWTimeout(f"el sitio rechazó el usuario: {error_msg.inner_text().strip()}")
                p.wait_for_timeout(300)
            if not campo_pass.is_visible():
                raise PWTimeout("tras escribir el correo y dar Continuar, no apareció el campo de contraseña")
        campo_pass.fill(password)
        # El éxito se decide por la respuesta JSON de /user/loginViaUsername
        # (igual que el Creador de Marcas): status=Success e is_email=1. El sitio
        # luego redirige a la tienda pública, no al panel, así que no se espera /client.
        try:
            # El primer "Continuar" (solo correo) también llama a loginViaUsername con la
            # contraseña vacía y responde "Contraseña incorrecta"; si esa respuesta llega
            # tarde se confundiría con la buena. Solo cuenta la petición que lleva contraseña.
            def es_login_con_password(r) -> bool:
                if "/user/loginViaUsername" not in r.url:
                    return False
                cuerpo = parse_qs(r.request.post_data or "")
                return bool((cuerpo.get("password") or [""])[0])

            with p.expect_response(es_login_con_password, timeout=30_000) as info:
                continuar.click()
            resp = info.value
        except PWTimeout:
            raise PWTimeout("el sitio no respondió al enviar el login")
        try:
            j = resp.json()
        except Exception:
            # El sitio redirige tan rápido que el cuerpo puede ya no estar disponible;
            # con HTTP 200 la confirmación real es que /client/dashboard abra (abajo).
            j = {"status": "Success", "data": {"is_email": 1}} if resp.ok else {}
        data = j.get("data") or {}
        if not (j.get("status") == "Success" and str(data.get("is_email")) == "1"):
            if str(data.get("is_phone")) == "1":
                raise PWTimeout("el sitio pidió código OTP (login por teléfono); usa el correo en MKP_..._USUARIO")
            raise PWTimeout(f"login rechazado: {j.get('message') or f'HTTP {resp.status}'}")

        # Deja terminar la redirección del sitio antes de navegar (evita net::ERR_ABORTED).
        try:
            p.wait_for_url(lambda u: "/user/login" not in u, timeout=15_000)
            p.wait_for_load_state("load")
        except PWTimeout:
            pass
        self._esperar_red(5_000)
        self._ir(self.DASHBOARD_PATH)
        if "/login" in p.url:
            raise PWTimeout("el login respondió OK pero el panel /client redirige al login (¿usuario sin permisos de admin?)")
        self.log.info("Login exitoso en %s", self.base_url)

    def _ir(self, ruta: str) -> None:
        """goto tolerante: si la navegación se aborta (redirección o JS del panel
        en curso), espera y reintenta."""
        for intento in range(3):
            try:
                self.page.goto(self.base_url + ruta, wait_until="domcontentloaded")
                return
            except PWError as e:
                if "ERR_ABORTED" not in str(e) and "interrupted" not in str(e):
                    raise
                self.log.info("   navegación a %s abortada (intento %d), reintentando…", ruta, intento + 1)
                self._esperar_red(5_000)
                if self.page.url.split("?")[0].rstrip("/").endswith(ruta):
                    return

    def ir_a_proveedores(self) -> None:
        p = self.page
        self._ir(self.VENDOR_PATH)
        self._esperar_red()
        if "/login" in p.url:
            raise SystemExit("La sesión expiró (redirigió al login).")
        if not self._boton_agregar().count():
            # Por si la ruta directa no carga (SPA): entrar desde el dashboard + menú lateral.
            self.log.info("   entrando a Proveedores desde el menú lateral")
            self._ir(self.DASHBOARD_PATH)
            self._esperar_red()
            p.locator("a:visible").filter(has_text=re.compile(r"^\s*Proveedores\s*$")).first.click()
            self._esperar_red()
        self._boton_agregar().wait_for(state="visible")

    def _boton_agregar(self):
        return self.page.locator("a:visible, button:visible").filter(has_text=re.compile(r"^\s*Agregar\s*$")).first

    def _esperar_red(self, ms: int = 10_000) -> None:
        try:
            self.page.wait_for_load_state("networkidle", timeout=ms)
        except PWTimeout:
            pass

    # ══════════════════════════════════════════
    #  Búsqueda / verificación
    # ══════════════════════════════════════════
    def buscar(self, nombre: str):
        """Busca en las pestañas Activo / En espera / Bloqueado. Cada pestaña es un
        <a data-rel="<id de su tabla>"> y cada tabla tiene su propio buscador
        (input[aria-controls=<id>]); el de las pestañas no abiertas está oculto."""
        self.ir_a_proveedores()
        objetivo = norm(nombre)
        pestanas = self.page.evaluate("""() => Array.from(document.querySelectorAll('a.nav-link[data-rel]'))
            .map(a => ({rel: a.dataset.rel, texto: a.innerText.trim(),
                        total: ((a.querySelector('sup') || {}).innerText || '')}))""")
        if not pestanas:      # sin pestañas: una sola tabla
            pestanas = [{"rel": "", "texto": "Activo", "total": ""}]
        for i, tab in enumerate(pestanas):
            etiqueta = re.sub(r"\s*\(\d+\)\s*$", "", tab["texto"]) or "Activo"
            if i > 0:
                if tab["total"].strip() == "(0)":
                    continue                      # pestaña vacía, no hace falta abrirla
                self.page.locator(f"a.nav-link[data-rel='{tab['rel']}']").click()
                self._esperar_red(6_000)
            tabla = f"#{tab['rel']}" if tab["rel"] else "table"
            caja = self.page.locator(f"input[aria-controls='{tab['rel']}']" if tab["rel"]
                                     else "input[placeholder*='Buscar' i]:visible").first
            try:
                caja.wait_for(state="visible", timeout=10_000)
            except PWTimeout:
                self.log.info("   (no se pudo usar el buscador de la pestaña '%s')", etiqueta)
                continue
            caja.fill("")
            caja.press_sequentially(nombre, delay=10)
            caja.press("Enter")
            self._esperar_red(8_000)
            self.page.wait_for_timeout(1_200)
            for celdas in self.page.evaluate(JS_FILAS, tabla):
                if any(norm(c) == objetivo for c in celdas):
                    direccion = next((c for c in celdas if plus_code(c)), "")
                    return ProveedorEnSitio(nombre=nombre, direccion=direccion, pestana=etiqueta)
        return None

    # ══════════════════════════════════════════
    #  Alta
    # ══════════════════════════════════════════
    def _modal(self):
        # El título cambia por MKP ("Agregar vendors" en FAD, "Agregar Proveedores" en
        # UNEFARM); se reconoce por el botón Enviar o los campos propios del alta.
        m = self.page.locator(".modal.show, .modal.in, [role='dialog']:visible").filter(
            has=self.page.locator("#add_vendor_form, input[name='pincode'], input[name='order_pre_time']")).first
        m.wait_for(state="visible", timeout=15_000)
        return m

    def _campo(self, scope, etiqueta: str, objetivo: str = INPUT_VISIBLE, exacto: bool = True):
        for ex in ([True, False] if exacto else [False]):
            lab = scope.locator("xpath=" + _xp_etiqueta(etiqueta, ex)).first
            if lab.count():
                loc = lab.locator(f"xpath=following::{objetivo}[1]")
                if loc.count():
                    return loc
        raise ErrorAlta(f"No se encontró el campo '{etiqueta}' en el formulario")

    def _escribir(self, loc, valor: str, etiqueta: str, comparar=None) -> None:
        loc.scroll_into_view_if_needed()
        loc.fill(valor)
        leido = loc.input_value()
        ok = comparar(leido, valor) if comparar else leido.strip() == valor.strip()
        if not ok:
            raise ErrorAlta(f"'{etiqueta}' quedó como '{leido}' en vez de '{valor}'")

    def _direccion(self, modal, direccion: str) -> None:
        """Escribe la dirección, hace clic en la sugerencia de Google y espera
        a que se autollenen latitud/longitud."""
        campo = self._campo(modal, ET_DIRECCION)
        lat = self._campo(modal, ET_LAT)
        sugerencia = self.page.locator(".pac-container .pac-item:visible").first

        intentos = [direccion]
        pc = plus_code(direccion)
        if pc and pc != direccion:
            ciudad = direccion.replace(pc, "").strip(" ,").split(",")[0].strip()
            intentos.append(f"{pc} {ciudad}".strip())
        for texto in intentos:
            campo.scroll_into_view_if_needed()
            campo.click()
            campo.fill("")
            campo.press_sequentially(texto, delay=DELAY_TECLEO)
            try:
                sugerencia.wait_for(state="visible", timeout=TIMEOUT_AUTOCOMPLETE)
            except PWTimeout:
                continue
            sugerencia.click()
            if self._esperar_valor(lat):
                return
            # Plan B: teclado (algunas versiones del autocomplete solo responden así).
            campo.click()
            campo.press("ArrowDown")
            campo.press("Enter")
            if self._esperar_valor(lat):
                return
        raise ErrorAlta("Google no devolvió sugerencia para la dirección o no se autollenó latitud/longitud")

    def _esperar_valor(self, loc, ms: int = TIMEOUT_AUTOCOMPLETE) -> bool:
        fin = time.time() + ms / 1000
        while time.time() < fin:
            if loc.input_value().strip():
                return True
            self.page.wait_for_timeout(250)
        return False

    def _toggle(self, scope, etiqueta: str, quiero: bool) -> None:
        chk = self._campo(scope, etiqueta, "input[@type='checkbox']", exacto=False)
        if chk.evaluate(JS_TOGGLE, quiero) != quiero:
            raise ErrorAlta(f"No se pudo dejar '{etiqueta}' en {'ON' if quiero else 'OFF'}")

    def _mostrar_avanzados(self, modal) -> None:
        try:
            visible = self._campo(modal, ET_PREPARACION, exacto=False).is_visible()
        except ErrorAlta:
            visible = False
        if not visible:
            boton = modal.get_by_text(re.compile(r"detalles avanzados|avanzad", re.I)).first
            if boton.count():
                boton.click()
                self.page.wait_for_timeout(500)

    def _boton_guardar(self, modal):
        exacto = modal.locator("#add_vendor_form:visible").first   # botón "Enviar" real de FAD
        if exacto.count():
            return exacto
        candidatos = modal.locator("button:visible, input[type='submit']:visible, a.btn:visible")
        elegido = None
        for i in range(candidatos.count()):
            b = candidatos.nth(i)
            texto = (b.inner_text() or b.get_attribute("value") or "").strip()
            if RE_BOTON_GUARDAR.search(texto) and not RE_BOTON_EXCLUIR.search(texto):
                elegido = b
        if elegido is None:
            raise ErrorAlta("No se encontró el botón de guardar del formulario")
        return elegido

    def alta(self, prov) -> ResultadoAlta:
        res = ResultadoAlta()
        self.ir_a_proveedores()
        self._boton_agregar().click()
        modal = self._modal()
        try:
            self._escribir(self._campo(modal, ET_NOMBRE), prov.nombre, ET_NOMBRE)
            self._escribir(self._campo(modal, ET_CORREO), prov.correo, ET_CORREO)
            self._escribir(self._campo(modal, ET_TELEFONO, "input[@type='tel']"), prov.telefono, ET_TELEFONO,
                           comparar=lambda leido, v: re.sub(r"\D", "", leido).endswith(v))
            self._direccion(modal, prov.direccion)
            self._escribir(self._campo(modal, ET_CP), prov.cp, ET_CP)
            self._escribir(self._campo(modal, ET_PAIS), prov.pais, ET_PAIS)
            for et in (ET_CIUDAD, ET_ESTADO, ET_LNG):
                if not self._campo(modal, et).input_value().strip():
                    res.advertencias.append(f"'{et}' quedó vacío tras el autocompletado")
            if prov.descripcion:
                self._escribir(self._campo(modal, ET_DESCRIPCION, "textarea"), prov.descripcion, ET_DESCRIPCION)

            self._mostrar_avanzados(modal)
            self._toggle(modal, ET_24_7, prov.disponible_24_7)
            self._escribir(self._campo(modal, ET_PREPARACION, exacto=False),
                           str(prov.tiempo_preparacion), "Tiempo de preparación")

            cat = self.page.evaluate(JS_CATEGORIAS)
            if not cat["encontrado"]:
                res.advertencias.append("No se encontró la lista de categorías (no se activaron)")
            elif cat["apagadas"]:
                res.advertencias.append(f"{cat['apagadas']} de {cat['total']} categorías quedaron apagadas")
            else:
                self.log.info("   categorías: %d activas (%d activadas ahora)", cat["total"], cat["activadas"])

            self._boton_guardar(modal).click()
            try:
                modal.wait_for(state="hidden", timeout=TIMEOUT_GUARDAR)
            except PWTimeout:
                errores = self.page.evaluate(JS_ERRORES)
                raise ErrorAlta("El formulario no se cerró al guardar"
                                + (f": {' | '.join(errores)}" if errores else ""))
            self._esperar_red()
            errores = [e for e in self.page.evaluate(JS_ERRORES) if re.search(r"error|inv[aá]lid|ya existe|taken", e, re.I)]
            if errores:
                raise ErrorAlta("El panel mostró error al guardar: " + " | ".join(errores))
        except ErrorAlta:
            self._captura(f"fila{prov.fila}_{_archivo_seguro(prov.nombre)}")
            self._cerrar_modal()
            raise
        except PWTimeout as e:
            self._captura(f"fila{prov.fila}_{_archivo_seguro(prov.nombre)}")
            self._cerrar_modal()
            raise ErrorAlta(f"Tiempo de espera agotado: {str(e).splitlines()[0]}")
        return res

    def _cerrar_modal(self) -> None:
        try:
            self.page.keyboard.press("Escape")
            cerrar = self.page.locator(".modal.show .close, .modal.show .btn-close, .modal.show [data-dismiss='modal']").first
            if cerrar.count() and cerrar.is_visible():
                cerrar.click()
        except Exception:
            pass

    def _volcar_html(self, nombre: str) -> None:
        try:
            ERRORES_DIR.mkdir(parents=True, exist_ok=True)
            (ERRORES_DIR / f"{nombre}.html").write_text(self.page.content(), encoding="utf-8")
        except Exception:
            pass

    def _captura(self, nombre: str) -> None:
        try:
            ERRORES_DIR.mkdir(parents=True, exist_ok=True)
            self.page.screenshot(path=str(ERRORES_DIR / f"{nombre}.png"), full_page=True)
        except Exception:
            pass

    # ══════════════════════════════════════════
    #  Diagnóstico (no guarda nada)
    # ══════════════════════════════════════════
    def diagnosticar(self, prov) -> None:
        d = self.diag_dir
        d.mkdir(parents=True, exist_ok=True)
        self.ir_a_proveedores()
        (d / "diag_lista_proveedores.html").write_text(self.page.content(), encoding="utf-8")
        self.page.screenshot(path=str(d / "diag_lista_proveedores.png"), full_page=True)
        filas = self.page.evaluate(JS_FILAS)
        self.log.info("Lista de proveedores: %d filas visibles. Ejemplo: %s", len(filas), filas[0] if filas else "-")

        self._boton_agregar().click()
        modal = self._modal()
        (d / "diag_modal_agregar.html").write_text(modal.evaluate("e => e.outerHTML"), encoding="utf-8")
        self._mostrar_avanzados(modal)

        self.log.info("── Campos del formulario ──")
        revisar = [(ET_NOMBRE, INPUT_VISIBLE, True), (ET_CORREO, INPUT_VISIBLE, True),
                   (ET_TELEFONO, "input[@type='tel']", True), (ET_DIRECCION, INPUT_VISIBLE, True),
                   (ET_CP, INPUT_VISIBLE, True), (ET_LAT, INPUT_VISIBLE, True), (ET_LNG, INPUT_VISIBLE, True),
                   (ET_CIUDAD, INPUT_VISIBLE, True), (ET_ESTADO, INPUT_VISIBLE, True), (ET_PAIS, INPUT_VISIBLE, True),
                   (ET_DESCRIPCION, "textarea", True), (ET_24_7, "input[@type='checkbox']", False),
                   (ET_PREPARACION, INPUT_VISIBLE, False)]
        for et, obj, exacto in revisar:
            try:
                loc = self._campo(modal, et, obj, exacto)
                info = loc.evaluate("e => `${e.tagName.toLowerCase()} name=${e.name||'-'} id=${e.id||'-'} type=${e.type||'-'}`")
                self.log.info("  OK   %-22s -> %s", et, info)
            except ErrorAlta:
                self.log.info("  FALTA %-21s", et)

        cat = self.page.evaluate("""() => { const c = document.querySelector('.custom-dd.dd.nestable_list_1');
            return c ? c.querySelectorAll('input[type=checkbox]').length : -1; }""")
        self.log.info("Categorías: %s", "contenedor NO encontrado" if cat < 0 else f"{cat} checkboxes")
        try:
            b = self._boton_guardar(modal)
            self.log.info("Botón guardar: '%s'", b.inner_text().strip())
        except ErrorAlta as e:
            self.log.info("Botón guardar: %s", e)

        # Prueba del autocompletado con el primer proveedor del Excel.
        try:
            self._direccion(modal, prov.direccion)
            valores = {et: self._campo(modal, et).input_value() for et in (ET_LAT, ET_LNG, ET_CIUDAD, ET_ESTADO, ET_PAIS, ET_CP)}
            self.log.info("Autocompletado con '%s': %s", prov.direccion, valores)
        except ErrorAlta as e:
            self.log.info("Autocompletado FALLÓ: %s", e)
        modal.screenshot(path=str(d / "diag_modal_agregar.png"))
        self.log.info("Diagnóstico guardado en %s (no se guardó ningún proveedor).", d)
        self._cerrar_modal()
