"""
Lectura de "Enlaces por nombre.xlsx" (proveedor → archivo de inventario) y escritura
de resultados por MKP (Estado / Observaciones / Fecha + color de fila).
"""
import re
import shutil
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill

from config import BACKUP_DIR, COLORES, OUTPUT_DIR

ALIAS_NOMBRE = ("nombre_proveedor", "nombre proveedor", "proveedor", "tienda", "nombre")
ALIAS_ARCHIVO = ("name_inventario", "inventario", "archivo", "csv")
PREFIJOS_RESULTADO = ("estado ", "observaciones ", "fecha ")


def norm(s) -> str:
    """minúsculas, sin acentos, espacios colapsados (solo para sugerir parecidos)."""
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip().lower()


def limpiar(s) -> str:
    """Texto tal cual, solo sin espacios sobrantes. Los nombres se comparan EXACTO."""
    return re.sub(r"\s+", " ", str(s or "")).strip()


@dataclass
class Fila:
    fila: int
    nombre: str
    archivo: str
    errores: list = field(default_factory=list)


class LibroEnlaces:
    def __init__(self, ruta: Path, mkp: str):
        self.ruta = Path(ruta)
        self.mkp = mkp
        self.destino = self.ruta
        self.wb = load_workbook(self.ruta)
        self.ws = self.wb.worksheets[0]
        self.col_nombre, self.col_archivo = self._detectar_columnas()
        self.ultima_col_datos = max(self.col_nombre, self.col_archivo)
        self.col_estado = self._col_resultado(f"Estado {mkp}")
        self.col_obs = self._col_resultado(f"Observaciones {mkp}")
        self.col_fecha = self._col_resultado(f"Fecha {mkp}")

    def _detectar_columnas(self):
        col_nombre = col_archivo = None
        for c in self.ws[1]:
            h = norm(c.value)
            if not h or h.startswith(PREFIJOS_RESULTADO):
                continue
            if col_archivo is None and any(a in h for a in ALIAS_ARCHIVO):
                col_archivo = c.column
            elif col_nombre is None and any(a in h for a in ALIAS_NOMBRE):
                col_nombre = c.column
        return col_nombre or 1, col_archivo or 2

    def _col_resultado(self, titulo: str) -> int:
        for c in self.ws[1]:
            if norm(c.value) == norm(titulo):
                return c.column
        col = max(self.ws.max_column, 2) + 1
        c = self.ws.cell(row=1, column=col, value=titulo)
        c.font = Font(bold=True)
        self.ws.column_dimensions[c.column_letter].width = 60 if "Observ" in titulo else 18
        return col

    def filas(self) -> list[Fila]:
        lista, vistos = [], {}
        for r in range(2, self.ws.max_row + 1):
            nombre = limpiar(self.ws.cell(row=r, column=self.col_nombre).value)
            archivo = limpiar(self.ws.cell(row=r, column=self.col_archivo).value)
            if not nombre and not archivo:
                continue
            f = Fila(fila=r, nombre=nombre, archivo=archivo)
            if not nombre:
                f.errores.append("Sin nombre de proveedor")
            if not archivo:
                f.errores.append("Sin nombre de archivo de inventario")
            if nombre and nombre in vistos:
                f.errores.append(f"Proveedor repetido en el Excel (fila {vistos[nombre]})")
            vistos.setdefault(nombre, r)
            lista.append(f)
        return lista

    def estado(self, fila: int) -> str:
        return limpiar(self.ws.cell(row=fila, column=self.col_estado).value).upper()

    def observaciones(self, fila: int) -> str:
        return limpiar(self.ws.cell(row=fila, column=self.col_obs).value)

    def marcar(self, fila: int, estado: str, observaciones: str = "") -> None:
        self.ws.cell(row=fila, column=self.col_estado, value=estado)
        self.ws.cell(row=fila, column=self.col_obs, value=observaciones or None)
        self.ws.cell(row=fila, column=self.col_fecha, value=datetime.now().strftime("%Y-%m-%d %H:%M"))
        relleno = PatternFill("solid", fgColor=COLORES.get(estado, "FFFFFF"))
        for col in range(1, max(self.ultima_col_datos, self.col_fecha) + 1):
            self.ws.cell(row=fila, column=col).fill = relleno
        self.guardar()

    def respaldar(self) -> Path:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        dst = BACKUP_DIR / f"{self.ruta.stem}_{datetime.now():%Y%m%d_%H%M%S}{self.ruta.suffix}"
        shutil.copy2(self.ruta, dst)
        return dst

    def guardar(self) -> None:
        try:
            self.wb.save(self.destino)
        except PermissionError:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            self.destino = OUTPUT_DIR / f"{self.ruta.stem}_resultado_{self.mkp}{self.ruta.suffix}"
            self.wb.save(self.destino)
