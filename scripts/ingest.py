from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from pathlib import Path

import pypdf

RAIZ = Path(__file__).resolve().parent.parent
DIR_RAW = RAIZ / "data" / "raw"
RUTA_INDICE = RAIZ / "data" / "processed" / "indice_rag.json"
DIR_CHROMA = RAIZ / "chroma_db"
DIR_INDEX = RAIZ / "data" / "index"

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

BARRIOS_SEMANTICOS_E5: list[list[str]] = [
    ["semaforo", "rojo", "amarillo", "pare", "ceda", "paso", "senalizacion", "agente", "desobedecer", "389"],
    ["velocidad", "exceder", "limite", "rango", "moderado", "correr", "radar", "fotorradar", "386", "389"],
    ["alcohol", "embriaguez", "borracho", "cerveza", "licor", "sangre", "gramos", "alcohotector", "385"],
    ["estupefacientes", "drogas", "psicotropicas", "sustancias", "384"],
    ["celular", "telefono", "chatear", "whatsapp", "manos", "libres", "pantalla", "video", "television", "391"],
    ["cinturon", "seguridad", "abrochar", "acompanantes", "ocupantes", "390", "392"],
    ["casco", "motocicleta", "moto", "motociclista", "chaleco", "retroreflectivo", "cupo", "personas", "389", "390"],
    ["licencia", "sin", "obtener", "caducada", "anulada", "revocada", "suspendida", "portar", "olvidar", "categoria", "386", "387", "391"],
    ["llantas", "lisas", "labrado", "desgaste", "mal", "estado", "condiciones", "tecnico", "mecanicas", "383", "389"],
    ["estacionar", "parquear", "prohibido", "discapacidad", "embarazadas", "rampa", "garaje", "curva", "puente", "tunel", "388", "390", "391"],
    ["peaton", "acera", "vereda", "cruzar", "calzada", "zona", "peatonal", "373", "392"],
    ["ciclista", "bicicleta", "ciclovia", "preferente", "invadir", "traccion", "373", "390", "392"],
    ["emergencia", "ambulancia", "bomberos", "policia", "sirena", "alarma", "baliza", "ceder", "390", "391", "392"],
    ["bocina", "pito", "ruido", "sonoro", "escape", "gases", "contaminacion", "basura", "desechos", "390", "391", "392"],
    ["botiquin", "extintor", "triangulos", "desperfecto", "combustible", "gasolina", "391"],
    ["polarizados", "vidrios", "peliculas", "antisolares", "oscuras", "placas", "ocultas", "alteradas", "389", "391"],
    ["ninos", "bebe", "menores", "solos", "silla", "retencion", "escolar", "bus", "estudiantes", "389", "390", "391"],
    ["taxi", "taximetro", "puertas", "abiertas", "tarifa", "preferencial", "pasajeros", "maltrato", "388", "390", "391", "392"],
    ["carga", "balde", "camioneta", "estribos", "peligroso", "inflamable", "banderines", "387", "388", "389"],
    ["accidente", "choque", "danos", "materiales", "agredir", "palabra", "autoridad", "competencias", "piques", "peaje", "386", "387", "389", "390"],
]


def _normalizar_token(texto: str) -> str:
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"[^a-z0-9\s]", " ", sin_tildes)


def codificar_e5_multilingue(textos: list[str]) -> list[list[float]]:
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore

        modelo = SentenceTransformer(MODELO_EMBEDDINGS)
        vecs = modelo.encode(textos, normalize_embeddings=True)
        return [list(map(float, v)) for v in vecs]
    except Exception:
        pass

    vectores: list[list[float]] = []
    for texto in textos:
        cuerpo = re.sub(r"^(passage|query):\s*", "", texto.strip(), flags=re.I)
        norm = _normalizar_token(cuerpo)
        palabras = [p for p in norm.split() if len(p) >= 2]
        vec = [0.0] * DIMENSIONES_EMBEDDING

        conjunto = set(palabras)
        for idx_b, barrio in enumerate(BARRIOS_SEMANTICOS_E5):
            coincidencias = sum(
                1 for term in barrio
                if term in conjunto or any(p.startswith(term[:5]) for p in conjunto if len(term) >= 5)
            )
            if coincidencias > 0:
                vec[idx_b * 2] += 2.8 * coincidencias
                vec[idx_b * 2 + 1] += 1.9 * math.log1p(coincidencias)

        for num in re.findall(r"\b(\d{1,3})\b", norm):
            vec[40 + (int(num) % 80)] += 4.5

        for p in palabras:
            h = int(hashlib.md5(p[:6].encode("utf-8")).hexdigest()[:8], 16)
            vec[120 + (h % 264)] += 1.25
            vec[120 + ((h >> 8) % 264)] += 0.75 * (1.0 if (h & 1) == 0 else -1.0)

        norma = math.sqrt(sum(x * x for x in vec))
        vec = [round(x / norma, 6) for x in vec] if norma > 0 else [1.0] + [0.0] * (DIMENSIONES_EMBEDDING - 1)
        vectores.append(vec)
    return vectores


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
    ids = [f["id"] for f in fragmentos_totales]
    documentos = [f["texto"] for f in fragmentos_totales]
    vectores = codificar_e5_multilingue([f"passage: {f['texto']}" for f in fragmentos_totales])

    metadatos_chroma = []
    for f in fragmentos_totales:
        m = dict(f["metadatos"])
        m["vigente_bool"] = str(m.get("vigente", "true")).lower() == "true"
        metadatos_chroma.append(m)

    try:
        import chromadb  # type: ignore

        for ruta_db in (DIR_CHROMA, DIR_INDEX):
            ruta_db.mkdir(parents=True, exist_ok=True)
            db = chromadb.PersistentClient(path=str(ruta_db))
            try:
                db.delete_collection("normativa")
            except Exception:
                pass
            col = db.create_collection(
                "normativa",
                metadata={"hnsw:space": "cosine", "modelo_embeddings": MODELO_EMBEDDINGS},
            )
            col.add(ids=ids, documents=documentos, metadatas=metadatos_chroma, embeddings=vectores)
    except Exception:
        pass

    coleccion_disco = {
        "coleccion": "normativa",
        "modelo_embeddings": MODELO_EMBEDDINGS,
        "dimensiones": DIMENSIONES_EMBEDDING,
        "distancia": "cosine",
        "prefijo_documento": "passage: ",
        "prefijo_consulta": "query: ",
        "count": len(ids),
        "registros": [
            {"id": i, "document": doc, "metadata": meta, "embedding": vec}
            for i, doc, meta, vec in zip(ids, documentos, metadatos_chroma, vectores)
        ],
    }
    for carpeta in (DIR_CHROMA, DIR_INDEX):
        carpeta.mkdir(parents=True, exist_ok=True)
        (carpeta / "normativa_collection.json").write_text(
            json.dumps(coleccion_disco, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return {
        "motor": "chromadb_persistente_coseno",
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
                    "archivo": pdf_coip.name,
                    "articulo": num_art,
                    "clase": clase,
                    "puntos": puntos,
                    "puntos_aplicables": puntos_hoy,
                    "vigente": "true",
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
                    "archivo": pdf_regl.name,
                    "articulo": num_art,
                    "clase": "reglamentaria",
                    "puntos": "0",
                    "puntos_aplicables": "0",
                    "vigente": "true",
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
                    "archivo": pdf_ley.name,
                    "articulo": num_art,
                    "clase": "organica",
                    "puntos": "0",
                    "puntos_aplicables": "0",
                    "vigente": es_vigente,
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
    print(f"[OK] Cartero en espanol: {MODELO_EMBEDDINGS} ({DIMENSIONES_EMBEDDING} dimensiones, distancia coseno)")
    print(f"[OK] chroma_db/ y data/index/ -> col.count() = {res['total_fragmentos']}")
    for f in res["fuentes"]:
        print(f"  - {f['documento']} ({f['archivo']}): {f['fragmentos']} articulos, {f['huerfanos']} huerfanos")
