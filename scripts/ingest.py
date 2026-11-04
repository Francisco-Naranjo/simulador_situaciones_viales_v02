from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pypdf

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

RAIZ = Path(__file__).resolve().parent.parent
DIR_RAW = RAIZ / "data" / "raw"
RUTA_INDICE = RAIZ / "data" / "processed" / "indice_rag.json"
DIR_CHROMA = RAIZ / "chroma_db"

MODELO_EMBEDDINGS = "intfloat/multilingual-e5-small"
DIMENSIONES_EMBEDDING = 384

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

_MODELO = None


def obtener_modelo_embeddings():
    global _MODELO
    if _MODELO is None:
        from sentence_transformers import SentenceTransformer
        try:
            _MODELO = SentenceTransformer(MODELO_EMBEDDINGS, local_files_only=True)
        except Exception:
            _MODELO = SentenceTransformer(MODELO_EMBEDDINGS)
    return _MODELO


def codificar_e5_multilingue(textos: list[str]) -> list[list[float]]:
    modelo = obtener_modelo_embeddings()
    vecs = modelo.encode(textos, normalize_embeddings=True, show_progress_bar=False)
    return [list(map(float, v)) for v in vecs]


def limpiar_cabeceras_pies(texto: str) -> str:
    patrones_cabecera = [
        re.compile(r"^registro\s+oficial.*$", re.I),
        re.compile(r"^p[aá]gina\s+\d+\s+de\s+\d+.*$", re.I),
        re.compile(r"^\s*-\s*\d+\s*-\s*$"),
        re.compile(r"^lexis\s+s\.?a\.?.*$", re.I),
    ]
    return "\n".join(
        linea for linea in texto.splitlines()
        if not any(p.match(linea.strip()) for p in patrones_cabecera)
    )


def limpiar_texto(texto: str) -> str:
    texto = limpiar_cabeceras_pies(texto)
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
    fragmentos: list[tuple[str, str]] = []
    for p in PATRON_CORTE.split(texto):
        limpio = limpiar_texto(p)
        if not limpio:
            continue
        m = CABECERA_ART.match(limpio)
        if m:
            fragmentos.append((m.group(1), limpio))
    huerfanos = sum(1 for _, txt in fragmentos if not CABECERA_ART.match(txt))
    return fragmentos, huerfanos


def extraer_pdf(ruta: Path) -> str:
    lector = pypdf.PdfReader(str(ruta))
    return "\n".join(p.extract_text() or "" for p in lector.pages)


def guardar_en_chromadb(fragmentos_totales: list[dict]) -> dict:
    import chromadb

    seen: dict[str, int] = {}
    for f in fragmentos_totales:
        fid = f["id"]
        if fid in seen:
            seen[fid] += 1
            f["id"] = f"{fid}_{seen[fid]}"
        else:
            seen[fid] = 1

    ids = [f["id"] for f in fragmentos_totales]
    documentos = [f["texto"] for f in fragmentos_totales]
    vectores = codificar_e5_multilingue([f"passage: {f['texto']}" for f in fragmentos_totales])

    metadatos_chroma = []
    for f in fragmentos_totales:
        m = dict(f["metadatos"])
        m["vigente_bool"] = str(m.get("vigente", "true")).lower() == "true"
        metadatos_chroma.append(m)

    DIR_CHROMA.mkdir(parents=True, exist_ok=True)
    db = chromadb.PersistentClient(path=str(DIR_CHROMA))
    try:
        db.delete_collection("normativa")
    except Exception:
        pass
    col = db.create_collection(
        "normativa",
        metadata={"hnsw:space": "cosine", "modelo_embeddings": MODELO_EMBEDDINGS},
    )
    col.add(ids=ids, documents=documentos, metadatas=metadatos_chroma, embeddings=vectores)

    coleccion_disco = {
        "coleccion": "normativa",
        "modelo_embeddings": MODELO_EMBEDDINGS,
        "dimensiones": DIMENSIONES_EMBEDDING,
        "distancia": "cosine",
        "count": len(ids),
    }
    (DIR_CHROMA / "normativa_collection.json").write_text(
        json.dumps(coleccion_disco, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "motor": "chromadb_persistent_cosine",
        "modelo_embeddings": MODELO_EMBEDDINGS,
        "dimensiones": DIMENSIONES_EMBEDDING,
        "distancia": "cosine",
        "count": len(ids),
    }


def construir_indice() -> dict:
    fragmentos_totales = []
    resumen_fuentes = []

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
                    "seccion": f"Capítulo Octavo · Infracciones de Tránsito, Art. {num_art}",
                    "archivo": pdf_coip.name,
                    "articulo": num_art,
                    "clase": clase,
                    "puntos": puntos,
                    "puntos_aplicables": puntos_hoy,
                    "vigente": "true",
                    "url": "https://www.defensa.gob.ec/wp-content/uploads/downloads/2021/03/COIP_act_feb-2021.pdf",
                },
            })
        resumen_fuentes.append({"documento": "COIP", "archivo": pdf_coip.name, "fragmentos": len(ares), "huerfanos": huerfanos})

    pdf_regl = DIR_RAW / "REGLAMENTO_A_LA_LEY_DE_TRANSPORTE_TERRESTRE_TRANSITO_Y_SEGURIDAD_VIAL.pdf"
    if pdf_regl.exists():
        ares, huerfanos = cortar_por_articulo(extraer_pdf(pdf_regl))
        for num_art, txt in ares:
            fragmentos_totales.append({
                "id": f"REGL-LOTTTSV-ART-{num_art}",
                "texto": txt,
                "metadatos": {
                    "documento": "Reglamento LOTTTSV",
                    "seccion": f"Reglamento General de Aplicación a la LOTTTSV, Art. {num_art}",
                    "archivo": pdf_regl.name,
                    "articulo": num_art,
                    "clase": "reglamentaria",
                    "puntos": "0",
                    "puntos_aplicables": "0",
                    "vigente": "true",
                    "url": "https://www.ant.gob.ec/reglamento-a-la-ley-de-transporte-terrestre-transito-y-seguridad-vial/",
                },
            })
        resumen_fuentes.append({"documento": "Reglamento LOTTTSV", "archivo": pdf_regl.name, "fragmentos": len(ares), "huerfanos": huerfanos})

    pdf_ley = DIR_RAW / "LEY-1-LEY-ORGANICA-DE-TRANSPORTE-TERRESTRE-Y-SEGURIDAD-VIAL.pdf"
    if pdf_ley.exists():
        ares, huerfanos = cortar_por_articulo(extraer_pdf(pdf_ley))
        for num_art, txt in ares:
            try:
                n = int(float(num_art))
            except ValueError:
                n = 0
            es_vigente = "false" if 106 <= n <= 180 else "true"
            fragmentos_totales.append({
                "id": f"LOTTTSV-ART-{num_art}",
                "texto": txt,
                "metadatos": {
                    "documento": "LOTTTSV",
                    "seccion": f"Ley Orgánica de Transporte Terrestre, Tránsito y Seguridad Vial, Art. {num_art}",
                    "archivo": pdf_ley.name,
                    "articulo": num_art,
                    "clase": "organica",
                    "puntos": "0",
                    "puntos_aplicables": "0",
                    "vigente": es_vigente,
                    "url": "https://www.obraspublicas.gob.ec/wp-content/uploads/downloads/2021/08/LOTTTSV-2021.pdf",
                },
            })
        resumen_fuentes.append({"documento": "LOTTTSV", "archivo": pdf_ley.name, "fragmentos": len(ares), "huerfanos": huerfanos})

    info_chroma = guardar_en_chromadb(fragmentos_totales)

    RUTA_INDICE.parent.mkdir(parents=True, exist_ok=True)
    datos = {
        "estrategia_corte": "Por artículo (?=Art\\.\\s*\\d+\\.-)",
        "modelo_embeddings": MODELO_EMBEDDINGS,
        "dimensiones_embedding": DIMENSIONES_EMBEDDING,
        "metrica_distancia": "cosine",
        "total_fragmentos": len(fragmentos_totales),
        "huerfanos": sum(r["huerfanos"] for r in resumen_fuentes),
        "chromadb": info_chroma,
        "fuentes": resumen_fuentes,
        "fragmentos": fragmentos_totales,
    }
    RUTA_INDICE.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return datos


if __name__ == "__main__":
    res = construir_indice()
    print(f"[OK] {res['total_fragmentos']} articulos detectados ({res['huerfanos']} huerfanos)")
    print(f"[OK] Embeddings reales: {MODELO_EMBEDDINGS} ({DIMENSIONES_EMBEDDING} dimensiones, distancia coseno)")
    print(f"[OK] ChromaDB persistente en {DIR_CHROMA}")
    for f in res["fuentes"]:
        print(f"  - {f['documento']} ({f['archivo']}): {f['fragmentos']} articulos, {f['huerfanos']} huerfanos")
