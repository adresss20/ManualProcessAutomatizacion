"""
Cliente HTTP directo (sin navegador) para el panel /client de Farmacias a Domicilio y
UNEFARM. Misma base que el Creador de cobertura (login + listado de proveedores),
más la importación de inventario por CSV. Pensado para el proyecto MKP integrado.

Endpoints (verificados en el HTML del panel y su JS público):
  POST /user/loginViaUsername              login AJAX; éxito = status Success + is_email 1
  GET  /client/vendor/filterdata?status=N  JSON DataTables: id, name… (1 Activo, 0 En espera, 2 Bloqueado)
  GET  /client/vendor/catalogs/{id}        pestaña Catálogo: form #save_imported_products
                                           (modal "Agregar servicio") + historial de importaciones
  POST /client/product/importCSV           multipart con los campos de ese form + el CSV;
                                           responde JSON {status: 'success'|…, message}
"""
import html
import re
import time

import requests
from bs4 import BeautifulSoup

from excel_io import limpiar

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36")
ESTADOS_VENDOR = {1: "Activo", 0: "En espera de aprobación", 2: "Bloqueado"}

RE_EST_OK = re.compile(r"success|complet|[ée]xito|exitos|termin|done|finish", re.I)
RE_EST_ERROR = re.compile(r"fail|error|fall|rechaz|invalid", re.I)


class ErrorMKP(Exception):
    """Fallo de una operación en el panel (el mensaje va a Observaciones)."""


class SesionExpirada(Exception):
    pass


def clasificar_estado(texto: str) -> str:
    """'OK' | 'ERROR' | 'EN PROCESO' según el texto de la columna Estado del historial."""
    if RE_EST_ERROR.search(texto or ""):
        return "ERROR"
    if RE_EST_OK.search(texto or ""):
        return "OK"
    return "EN PROCESO"


class ClienteFAD:
    def __init__(self, base_url: str, log, timeout: int = 60):
        self.base_url = base_url.rstrip("/")
        self.log = log
        self.timeout = timeout
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA, "Accept-Language": "es-MX,es;q=0.9,en;q=0.8"})
        self._credenciales = None

    # ── utilidades ─────────────────────────────
    def url(self, ruta: str) -> str:
        return ruta if ruta.startswith("http") else self.base_url + ruta

    def get(self, ruta: str, **kw) -> requests.Response:
        r = self.s.get(self.url(ruta), timeout=self.timeout, **kw)
        if "/user/login" in r.url:
            raise SesionExpirada()
        return r

    def con_reintento(self, fn, *a, **kw):
        """Ejecuta fn; si la sesión expiró, vuelve a iniciar sesión una vez y reintenta."""
        try:
            return fn(*a, **kw)
        except SesionExpirada:
            self.log.info("   la sesión expiró; iniciando sesión de nuevo…")
            self.login(*self._credenciales)
            return fn(*a, **kw)

    # ── login ─────────────────────────────────
    def login(self, usuario: str, password: str) -> None:
        self._credenciales = (usuario, password)
        r = self.s.get(self.url("/user/login"), timeout=self.timeout)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        form = soup.find("form", id="login-form-new") or next(
            (f for f in soup.find_all("form") if f.find("input", {"name": "password"})), None)
        if form is None:
            raise SystemExit("No se encontró el formulario de login en /user/login.")
        datos = {i.get("name"): (i.get("value") or "") for i in form.find_all("input") if i.get("name")}
        datos["username"] = usuario
        datos["password"] = password
        r2 = self.s.post(self.url("/user/loginViaUsername"), data=datos, timeout=self.timeout, headers={
            "X-Requested-With": "XMLHttpRequest", "X-CSRF-TOKEN": datos.get("_token", ""),
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Referer": self.url("/user/login"), "Origin": self.base_url})
        try:
            j = r2.json()
        except ValueError:
            raise SystemExit(f"No se pudo iniciar sesión: respuesta no-JSON (HTTP {r2.status_code}).")
        data = j.get("data") or {}
        if not (j.get("status") == "Success" and str(data.get("is_email")) == "1"):
            if str(data.get("is_phone")) == "1":
                raise SystemExit("No se pudo iniciar sesión: el sitio pidió código OTP; usa el correo.")
            raise SystemExit(f"No se pudo iniciar sesión: {j.get('message') or f'HTTP {r2.status_code}'}")
        try:
            self.get("/client/dashboard")
        except SesionExpirada:
            raise SystemExit("El login respondió OK pero /client redirige al login (¿usuario sin permisos?).")
        self.log.info("Login exitoso en %s", self.base_url)

    # ── proveedores ───────────────────────────
    def _filterdata(self, status: int, start: int, largo: int) -> dict:
        r = self.get("/client/vendor/filterdata", params={
            "draw": 1, "start": start, "length": largo, "status": status, "search": "",
        }, headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"})
        try:
            return r.json()
        except ValueError:
            raise ErrorMKP(f"/client/vendor/filterdata no devolvió JSON (HTTP {r.status_code})")

    def proveedores(self) -> list[dict]:
        """Todos los proveedores de las 3 pestañas: [{id, nombre, pestana}]."""
        todos, largo = [], 200
        for status, pestana in ESTADOS_VENDOR.items():
            start = 0
            while True:
                j = self.con_reintento(self._filterdata, status, start, largo)
                filas = j.get("data") or []
                for f in filas:
                    todos.append({"id": f.get("id"), "pestana": pestana,
                                  "nombre": limpiar(html.unescape(str(f.get("name") or "")))})
                start += len(filas)
                total = int(j.get("recordsFiltered") or j.get("recordsTotal") or 0)
                if not filas or start >= total:
                    break
        return todos

    # ── catálogo / importación ────────────────
    def pagina_catalogo(self, vendor_id) -> dict:
        """Lee /client/vendor/catalogs/{id}: form de importación, token CSRF, historial
        de importaciones (# / Nombre del archivo / Estado / Enlace) y Total Servicios."""
        r = self.get(f"/client/vendor/catalogs/{vendor_id}")
        soup = BeautifulSoup(r.text, "html.parser")
        meta = soup.find("meta", {"name": "csrf-token"})
        form = soup.find("form", id="save_imported_products")
        campos, campo_archivo = {}, None
        if form:
            for i in form.find_all(["input", "select", "textarea"]):
                nombre = i.get("name")
                if not nombre:
                    continue
                if i.name == "input" and (i.get("type") or "").lower() == "file":
                    campo_archivo = campo_archivo or nombre
                elif i.name == "input" and (i.get("type") or "").lower() in ("checkbox", "radio"):
                    if i.has_attr("checked"):
                        campos[nombre] = i.get("value") or "on"
                elif i.name == "select":
                    op = i.find("option", selected=True) or i.find("option")
                    campos[nombre] = op.get("value", "") if op else ""
                else:
                    campos[nombre] = i.get("value") or i.get_text() or ""
        return {
            "html": r.text,
            "form": bool(form),
            "campos": campos,
            "campo_archivo": campo_archivo,
            "csrf": meta.get("content") if meta else campos.get("_token"),
            "historial": self._historial(soup),
            "total_servicios": self._total_servicios(soup),
        }

    @staticmethod
    def _historial(soup) -> list[dict]:
        """Historial de importaciones de PRODUCTOS. Ojo: la página tiene otra tabla igual
        ("Nombre del archivo") para la importación de vendors; se usa la del mismo modal
        que el form #save_imported_products."""
        form = soup.find("form", id="save_imported_products")
        modal = form.find_parent("div", class_="modal") if form else None
        tablas = (modal.find_all("table") if modal else []) or soup.find_all("table")
        for tabla in tablas:
            cab = [limpiar(th.get_text(" ")) .lower() for th in tabla.select("thead th")] or \
                  [limpiar(td.get_text(" ")).lower() for td in (tabla.find("tr") or soup.new_tag("tr")).find_all(["th", "td"])]
            if not any("nombre del archivo" in c or "file name" in c for c in cab):
                continue
            i_nom = next(i for i, c in enumerate(cab) if "nombre del archivo" in c or "file name" in c)
            i_est = next((i for i, c in enumerate(cab) if "estado" in c or "status" in c), None)
            filas = []
            for tr in tabla.select("tbody tr"):
                tds = tr.find_all("td")
                if len(tds) <= i_nom:
                    continue
                enlace = tr.find("a", href=True)
                errores = tr.find(class_="tooltip_error")     # detalle de errores del panel
                filas.append({
                    "id": tr.get("data-row-id") or limpiar(tds[0].get_text(" ")),
                    "archivo": limpiar(tds[i_nom].get_text(" ")),
                    "estado": limpiar(tds[i_est].get_text(" ")) if i_est is not None and len(tds) > i_est else "",
                    "enlace": enlace["href"] if enlace else "",
                    "errores": limpiar(errores.get_text(" | ", strip=True))[:400] if errores else "",
                })
            return filas
        return []

    @staticmethod
    def _total_servicios(soup):
        etiqueta = soup.find(string=re.compile(r"Total\s+Servicios", re.I))
        caja = etiqueta.parent if etiqueta else None
        for _ in range(4):
            if caja is None:
                break
            m = re.search(r"\b(\d[\d,]*)\b", caja.get_text(" "))
            if m:
                return int(m.group(1).replace(",", ""))
            caja = caja.parent
        return None

    def importar_csv(self, vendor_id, ruta) -> dict:
        """Sube el CSV como lo hace el modal "Agregar servicio" → Importar."""
        pag = self.pagina_catalogo(vendor_id)
        if not pag["form"] or not pag["campo_archivo"]:
            raise ErrorMKP("La página del proveedor no tiene el formulario de importación de CSV")
        with open(ruta, "rb") as fh:
            r = self.s.post(self.url("/client/product/importCSV"), data=pag["campos"],
                            files={pag["campo_archivo"]: (ruta.name, fh, "text/csv")},
                            timeout=max(self.timeout, 180), headers={
                                "X-CSRF-TOKEN": pag["csrf"] or "", "X-Requested-With": "XMLHttpRequest",
                                "Accept": "application/json",
                                "Referer": self.url(f"/client/vendor/catalogs/{vendor_id}"),
                                "Origin": self.base_url})
        if "/user/login" in r.url:
            raise SesionExpirada()
        try:
            j = r.json()
        except ValueError:
            raise ErrorMKP(f"El panel no respondió JSON al importar (HTTP {r.status_code})")
        if str(j.get("status", "")).lower() != "success":
            raise ErrorMKP(f"El panel rechazó el archivo: {j.get('message') or j.get('errors') or j}")
        return {"antes": pag, "respuesta": j}

    def esperar_importacion(self, vendor_id, archivo: str, previos: set,
                            espera: int, intervalo: int) -> dict:
        """Sondea el historial hasta que el archivo subido pase a OK/ERROR o se agote la espera.
        `previos` = nombres de archivo que ya estaban en el historial antes de subir. El panel
        guarda cada subida con un prefijo numérico único ("1789607929_<nombre>.csv"), así
        que la fila nueva es la que no estaba antes (el # de fila cambia, no sirve)."""
        fin = time.time() + espera
        ultimo = None
        while True:
            pag = self.con_reintento(self.pagina_catalogo, vendor_id)
            nuevos = [h for h in pag["historial"] if h["archivo"] not in previos and h["archivo"].endswith(archivo)] \
                or [h for h in pag["historial"] if h["archivo"] not in previos]
            if nuevos:
                ultimo = nuevos[0]
                estado = clasificar_estado(ultimo["estado"])
                if estado != "EN PROCESO":
                    return {"estado": estado, "fila": ultimo, "pag": pag}
            if time.time() >= fin:
                return {"estado": "EN PROCESO" if ultimo else "SIN REGISTRO", "fila": ultimo, "pag": pag}
            time.sleep(intervalo)
