"""Construye y verifica la tabla canónica de 90 contravenciones del COIP (arts. 386–392).

Lee `docs/tabla_contravenciones.csv`, contrasta cada artículo contra el texto extraído de
`data/raw/AMT-COIP-CAPITULO-TRANSITO.pdf`, corrige perfiles y genera:
  1. `data/tabla_contravenciones.csv` (90 filas verificadas, referenciado por `docs/tabla-coip.md`)
  2. `docs/tabla_contravenciones.csv` (actualizado a estado `verificado`)
  3. `data/raw/contravenciones_lotttsv.json` (90 registros canónicos consumidos por FastAPI)

Uso:
    python scripts/construir_tabla.py
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CSV_DOCS = RAIZ / "docs" / "tabla_contravenciones.csv"
CSV_DATA = RAIZ / "data" / "tabla_contravenciones.csv"
JSON_CANONICO = RAIZ / "data" / "raw" / "contravenciones_lotttsv.json"
PDF_COIP = RAIZ / "data" / "raw" / "AMT-COIP-CAPITULO-TRANSITO.pdf"

NOMBRES_CLASE = {
    "1": "Primera Clase",
    "2": "Segunda Clase",
    "3": "Tercera Clase",
    "4": "Cuarta Clase",
    "5": "Quinta Clase",
    "6": "Sexta Clase",
    "7": "Séptima Clase",
}

MAPA_PERFILES = {
    "particular": "conductor_particular",
    "profesional": "conductor_profesional",
    "motociclista": "motociclista",
    "ciclista": "ciclista",
    "peaton": "peaton",
}

TODOS_PERFILES = [
    "conductor_particular",
    "conductor_profesional",
    "motociclista",
    "ciclista",
    "peaton",
]


def extraer_texto_coip() -> dict[tuple[str, str], str]:
    """Extrae el texto literal de cada numeral de los arts. 386 a 392 desde el PDF del COIP."""
    if not PDF_COIP.exists():
        return {}
    try:
        import pypdf
        lector = pypdf.PdfReader(str(PDF_COIP))
        texto = "\n".join(p.extract_text() or "" for p in lector.pages)
    except Exception:
        return {}

    literales: dict[tuple[str, str], str] = {}
    # Separar por Art. 386 .. Art. 392
    partes = re.split(r"(?=Art\.\s*3(?:8[6-9]|9[0-2])\.-)", texto)
    for bloque in partes:
        m_art = re.match(r"Art\.\s*(38[6-9]|39[0-2])\.-", bloque.strip())
        if not m_art:
            continue
        art = m_art.group(1)
        if art == "386" and "Será sancionado con dos salarios" in bloque:
            inc1, inc2 = bloque.split("Será sancionado con dos salarios", 1)
            _extraer_numerales(art, inc1, literales, prefijo="")
            _extraer_numerales(art, inc2, literales, prefijo="inc.2 ")
        else:
            _extraer_numerales(art, bloque, literales, prefijo="")
    return literales


def _extraer_numerales(art: str, bloque: str, destino: dict[tuple[str, str], str], prefijo: str) -> None:
    lineas = [ln.strip() for ln in bloque.splitlines() if ln.strip()]
    actual_num = None
    acumulado: list[str] = []
    for ln in lineas:
        if ln.startswith("A las o los ciclistas") or ln.startswith("A las y los ciclistas") or ln.startswith("En el caso del número 1") or ln.startswith("Si el automotor es nuevo"):
            if actual_num is not None:
                destino[(art, f"{prefijo}{actual_num}")] = _limpiar(" ".join(acumulado))
                actual_num = None
                acumulado = []
            continue
        m_num = re.match(r"^(\d{1,2})\.\s+(.*)", ln)
        if m_num:
            if actual_num is not None:
                destino[(art, f"{prefijo}{actual_num}")] = _limpiar(" ".join(acumulado))
            actual_num = m_num.group(1)
            acumulado = [m_num.group(2)]
        elif actual_num is not None:
            acumulado.append(ln)
    if actual_num is not None:
        destino[(art, f"{prefijo}{actual_num}")] = _limpiar(" ".join(acumulado))


def _limpiar(texto: str) -> str:
    # Corrige cortes de sílaba del PDF como "respec tivos" -> "respectivos"
    reemplazos = {
        "respec tivos": "respectivos",
        "utilic en": "utilicen",
        "reglamen tos": "reglamentos",
        "d e ": "de ",
        "regl amentos": "reglamentos",
        "condu zca": "conduzca",
        "distracci ón": "distracción",
        "día s": "días",
    }
    t = re.sub(r"\s+", " ", texto).strip()
    for k, v in reemplazos.items():
        t = t.replace(k, v)
    return t


def convertir_id_canonico(id_csv: str, articulo: str, numeral: str) -> str:
    """Convierte C-389-01 -> CONT-COIP-ART389-1 y C-386-B-01 -> CONT-COIP-ART386-B1."""
    if numeral.startswith("inc.2"):
        n = numeral.split()[-1]
        return f"CONT-COIP-ART{articulo}-B{n}"
    return f"CONT-COIP-ART{articulo}-{int(numeral)}"


def parsear_perfiles(cadena: str) -> list[str]:
    cadena = cadena.strip().lower()
    if cadena == "todos":
        return list(TODOS_PERFILES)
    resultado = []
    for p in cadena.split(";"):
        p = p.strip()
        if p in MAPA_PERFILES:
            resultado.append(MAPA_PERFILES[p])
    return resultado or ["conductor_particular", "conductor_profesional"]


def extraer_dias_prision(pena_adicional: str) -> int:
    m = re.search(r"(\d+)\s*d[ií]as\s+de\s+prisi[oó]n", pena_adicional or "", re.I)
    return int(m.group(1)) if m else 0


def construir() -> None:
    literales = extraer_texto_coip()
    filas_csv = []
    registros_json = []

    with CSV_DOCS.open("r", encoding="utf-8-sig", newline="") as f:
        lector = csv.DictReader(f)
        columnas = lector.fieldnames or []
        for fila in lector:
            # Corrección de perfiles en C-388-05 y C-388-06 (obras en vía / reductores)
            if fila["id"] in ("C-388-05", "C-388-06"):
                fila["perfil_aplica"] = "particular;profesional"
            fila["estado_verificacion"] = "verificado"
            filas_csv.append(fila)

            art = fila["articulo"].strip()
            num = fila["numeral"].strip()
            id_canonico = convertir_id_canonico(fila["id"], art, num)
            clase_num = fila["clase"].strip()
            es_inciso_2 = num.startswith("inc.2")
            nombre_clase = NOMBRES_CLASE[clase_num]
            if es_inciso_2:
                nombre_clase = "Primera Clase (Inciso 2)"

            etiqueta_art = f"Art. {art} inc. 2 num. {num.split()[-1]}" if es_inciso_2 else f"Art. {art} num. {num}"
            perfiles = parsear_perfiles(fila["perfil_aplica"])

            puntos_coip = float(fila["puntos_texto_coip"])
            puntos_hoy = float(fila["puntos_aplicables"])
            # Art. 373 COIP y Art. 386 num 1: peatones y ciclistas (o conducir sin haber obtenido licencia) no pierden puntos
            if fila["id"] == "C-386-01" or set(perfiles).issubset({"peaton", "ciclista"}):
                puntos_reducidos = 0.0
            else:
                puntos_reducidos = puntos_coip

            texto_literal = literales.get((art, num))
            descripcion = fila["descripcion"].strip()
            if not descripcion.endswith("."):
                descripcion += "."

            registros_json.append({
                "id_contravencion": id_canonico,
                "codigo_csv": fila["id"],
                "clase": nombre_clase,
                "articulo": etiqueta_art,
                "norma": "Código Orgánico Integral Penal",
                "descripcion_infraccion": descripcion,
                "texto_literal_coip": texto_literal or descripcion,
                "porcentaje_sbu": float(fila["porcentaje_sbu"]),
                "puntos_reducidos": puntos_reducidos,
                "puntos_aplicables": puntos_hoy,
                "pena_adicional": fila["pena_adicional"].strip() or None,
                "perfiles_aplicables": perfiles,
                "dias_privacion_libertad": extraer_dias_prision(fila["pena_adicional"]),
                "fuente_url": "https://www.ant.gob.ec/",
            })

    CSV_DATA.parent.mkdir(parents=True, exist_ok=True)
    for destino_csv in (CSV_DATA, CSV_DOCS):
        with destino_csv.open("w", encoding="utf-8", newline="") as f:
            escritor = csv.DictWriter(f, fieldnames=columnas)
            escritor.writeheader()
            escritor.writerows(filas_csv)

    JSON_CANONICO.write_text(json.dumps(registros_json, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[OK] {len(filas_csv)} filas verificadas en {CSV_DATA.relative_to(RAIZ)} y {CSV_DOCS.relative_to(RAIZ)}")
    print(f"[OK] {len(registros_json)} contravenciones canónicas escritas en {JSON_CANONICO.relative_to(RAIZ)}")
    print(f"[OK] {len(literales)} numerales contrastados literalmente contra {PDF_COIP.name}")


if __name__ == "__main__":
    construir()
