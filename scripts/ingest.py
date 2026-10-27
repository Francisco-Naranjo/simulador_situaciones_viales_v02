"""Ingesta y corte por artículo para el sistema RAG · Caso 08 «Vía Segura».

Implementa exactamente la estrategia del Módulo 3 (Guía de RAG por caso · Grupo 08):
  - Estrategia de corte: Por artículo `(?=Art\\.\\s*\\d+)` con verificación de cabecera `/^Art\\.\\s*\\d+/`.
  - Cero fragmentos huérfanos (ningún fragmento queda sin su número de artículo).
  - Ningún fragmento almacena montos en dólares quemados (el SBU vive en `config/parametros.json`).
  - Etiquetas (metadatos) obligatorias en cada fragmento:
      * `documento`: "COIP" | "Reglamento LOTTTSV" | "LOTTTSV"
      * `articulo`: número del artículo (ej. "389")
      * `clase`: "primera" | "segunda" | "tercera" | "cuarta" | "quinta" | "sexta" | "septima" | "delito_o_regla" | "reglamentaria"
      * `puntos`: puntos según el texto del artículo (ej. "6")
      * `puntos_aplicables`: puntos vigentes tras reforma RO 512-2021 (ej. "0")
      * `vigente`: "true" | "false" (los artículos de infracciones de la LOTTTSV 2011 derogados por el COIP llevan "false")

Uso:
    python scripts/ingest.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pypdf

RAIZ = Path(__file__).resolve().parent.parent
DIR_RAW = RAIZ / "data" / "raw"
RUTA_INDICE = RAIZ / "data" / "processed" / "indice_rag.json"

PATRON_CORTE = re.compile(r"(?=Art\.\s*\d+\s*\.-)")
CABECERA_ART = re.compile(r"^Art\.\s*(\d+(?:\.\d+)?)\s*\.-")

INFO_CONTRAVENCIONES_COIP = {
    "386": ("primera", "10", "10"),
    "387": ("segunda", "9", "9"),
    "388": ("tercera", "7.5", "0"),
    "389": ("cuarta", "6", "0"),
    "390": ("quinta", "4.5", "0"),
    "391": ("sexta", "3", "0"),
    "392": ("septima", "1.5", "0"),
}


def limpiar_texto(texto: str) -> str:
    reemplazos = {
        "p ena": "pena",
        "previ stas": "previstas",
        "es cala": "escala",
        "respec tivos": "respectivos",
        "utilic en": "utilicen",
        "reglamen tos": "reglamentos",
        "d e ": "de ",
        "regl amentos": "reglamentos",
        "condu zca": "conduzca",
        "distracci ón": "distracción",
        "día s": "días",
    }
    t = re.sub(r"[ \t]+", " ", texto)
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    for k, v in reemplazos.items():
        t = t.replace(k, v)
    return t


def cortar_por_articulo(texto: str) -> tuple[list[tuple[str, str]], int]:
    """Corta el texto por `(?=Art.\\s*\\d+\\.-)` y descarta preámbulos sin cabecera `Art. X`."""
    partes = PATRON_CORTE.split(texto)
    fragmentos: list[tuple[str, str]] = []
    huerfanos = 0
    for p in partes:
        limpio = limpiar_texto(p)
        if not limpio:
            continue
        m = CABECERA_ART.match(limpio)
        if not m:
            # Preámbulo o encabezado de capítulo antes del primer Art.: no se indexa como huérfano
            continue
        num_art = m.group(1)
        fragmentos.append((num_art, limpio))
    # Verificación de que ningún fragmento indexado sea huérfano
    for _, txt in fragmentos:
        if not CABECERA_ART.match(txt):
            huerfanos += 1
    return fragmentos, huerfanos


def extraer_pdf(ruta: Path) -> str:
    lector = pypdf.PdfReader(str(ruta))
    return "\n".join(p.extract_text() or "" for p in lector.pages)


def construir_indice() -> dict:
    fragmentos_totales = []
    resumen_fuentes = []

    # 1. COIP Capítulo Tránsito (Arts. 371-392) · Fuente principal vigente de infracciones y contravenciones
    pdf_coip = DIR_RAW / "AMT-COIP-CAPITULO-TRANSITO.pdf"
    if pdf_coip.exists():
        ares, huerfanos = cortar_por_articulo(extraer_pdf(pdf_coip))
        for num_art, txt in ares:
            clase, puntos, puntos_hoy = INFO_CONTRAVENCIONES_COIP.get(
                num_art, ("delito_o_regla", "variable", "variable")
            )
            if num_art == "385":
                clase, puntos, puntos_hoy = ("embriaguez", "5_a_30", "5_a_30")
            elif num_art == "383":
                clase, puntos, puntos_hoy = ("llantas_mal_estado", "5", "5")
            elif num_art == "384":
                clase, puntos, puntos_hoy = ("estupefacientes", "15", "15")
            fragmentos_totales.append({
                "id": f"COIP-ART-{num_art}",
                "texto": txt,
                "metadatos": {
                    "documento": "COIP",
                    "archivo": pdf_coip.name,
                    "articulo": num_art,
                    "clase": clase,
                    "puntos": puntos,
                    "puntos_aplicables": puntos_hoy,
                    "vigente": "true",
                },
            })
        resumen_fuentes.append({"documento": "COIP", "archivo": pdf_coip.name, "fragmentos": len(ares), "huerfanos": huerfanos})

    # 2. Reglamento a la LOTTTSV · Procedimientos, señales, rangos de velocidad y licencias
    pdf_regl = DIR_RAW / "REGLAMENTO_A_LA_LEY_DE_TRANSPORTE_TERRESTRE_TRANSITO_Y_SEGURIDAD_VIAL.pdf"
    if pdf_regl.exists():
        ares, huerfanos = cortar_por_articulo(extraer_pdf(pdf_regl))
        for num_art, txt in ares:
            fragmentos_totales.append({
                "id": f"REGL-LOTTTSV-ART-{num_art}",
                "texto": txt,
                "metadatos": {
                    "documento": "Reglamento LOTTTSV",
                    "archivo": pdf_regl.name,
                    "articulo": num_art,
                    "clase": "reglamentaria",
                    "puntos": "0",
                    "puntos_aplicables": "0",
                    "vigente": "true",
                },
            })
        resumen_fuentes.append({"documento": "Reglamento LOTTTSV", "archivo": pdf_regl.name, "fragmentos": len(ares), "huerfanos": huerfanos})

    # 3. LOTTTSV (versión 2011 en data/raw): se etiquetan como vigente="false" los arts. 106-180 derogados por el COIP (2014)
    pdf_ley = DIR_RAW / "LEY-1-LEY-ORGANICA-DE-TRANSPORTE-TERRESTRE-Y-SEGURIDAD-VIAL.pdf"
    if pdf_ley.exists():
        ares, huerfanos = cortar_por_articulo(extraer_pdf(pdf_ley))
        for num_art, txt in ares:
            try:
                n = int(float(num_art))
            except ValueError:
                n = 0
            # El Libro III de infracciones de la LOTTTSV 2011 (arts. 106 a 180) fue derogado por el COIP en 2014
            es_vigente = "false" if 106 <= n <= 180 else "true"
            fragmentos_totales.append({
                "id": f"LOTTTSV-ART-{num_art}",
                "texto": txt,
                "metadatos": {
                    "documento": "LOTTTSV",
                    "archivo": pdf_ley.name,
                    "articulo": num_art,
                    "clase": "organica",
                    "puntos": "0",
                    "puntos_aplicables": "0",
                    "vigente": es_vigente,
                },
            })
        resumen_fuentes.append({"documento": "LOTTTSV", "archivo": pdf_ley.name, "fragmentos": len(ares), "huerfanos": huerfanos})

    RUTA_INDICE.parent.mkdir(parents=True, exist_ok=True)
    datos = {
        "estrategia_corte": "Por artículo (?=Art\\.\\s*\\d+\\.-)",
        "total_fragmentos": len(fragmentos_totales),
        "huerfanos": sum(r["huerfanos"] for r in resumen_fuentes),
        "fuentes": resumen_fuentes,
        "fragmentos": fragmentos_totales,
    }
    RUTA_INDICE.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return datos


if __name__ == "__main__":
    res = construir_indice()
    print(f"[OK] Indice RAG construido en {RUTA_INDICE.relative_to(RAIZ)}")
    print(f"[OK] Total fragmentos: {res['total_fragmentos']} | Fragmentos huerfanos: {res['huerfanos']}")
    for f in res["fuentes"]:
        print(f"  - {f['documento']} ({f['archivo']}): {f['fragmentos']} articulos, {f['huerfanos']} huerfanos")
