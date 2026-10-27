"""Servicio de Recuperación Aumentada (RAG) · Caso 08 «Vía Segura».

Implementa las 5 misiones de la Guía de RAG por caso (Módulo 3):
  1. Fuentes reales indexadas en `data/processed/indice_rag.json` (generadas por `scripts/ingest.py`).
  2. Corte estructural por artículo (`Art. X.-`), garantizando 0 fragmentos huérfanos.
  3. Filtrado por etiquetas (`where`) ANTES del cálculo de `top_k` (nunca se recuperan artículos con `vigente="false"`).
  4. Búsqueda híbrida (coincidencia literal de número de artículo/código + similitud léxica BM25 y tesauro vial ciudadano).
  5. Regla de silencio («O citan la fuente, o guardan silencio»): abstención determinista cuando la consulta no tiene respaldo en las fuentes cargadas o requiere derivación a la ANT.
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
RUTA_INDICE = RAIZ / "data" / "processed" / "indice_rag.json"

MENSAJE_ABSTENCION_RAG = (
    "La normativa que tengo cargada (COIP, LOTTTSV y su Reglamento) no responde esta pregunta "
    "o requiere verificación administrativa. Le recomiendo consultar directamente a la Agencia Nacional de Tránsito (ANT)."
)

# Palabras vacías en español
VACIAS = {
    "como", "cual", "cuando", "cuanto", "cuantos", "donde", "para", "pero", "porque",
    "quien", "tengo", "puedo", "puede", "pasa", "paso", "sobre", "entre", "hasta",
    "desde", "este", "esta", "estos", "estas", "solo", "hacer", "hago", "dice", "segun",
    "una", "uno", "unos", "unas", "los", "las", "del", "por", "con", "sin", "que",
}

# Expansión de lenguaje ciudadano a términos técnicos del COIP/Reglamento
TESAURO_VIAL = {
    "rojo": ["semaforo", "señalizacion", "389"],
    "semaforo": ["semaforos", "señalizacion", "pare", "ceda", "389"],
    "pare": ["semaforos", "señalizacion", "ceda", "389"],
    "celular": ["telefono", "manos", "libres", "391"],
    "telefono": ["celular", "manos", "libres", "391"],
    "chatear": ["telefono", "celular", "manos", "libres", "391"],
    "alcohol": ["embriaguez", "gramos", "sangre", "385"],
    "borracho": ["embriaguez", "alcohol", "sangre", "385"],
    "embriaguez": ["alcohol", "gramos", "sangre", "385"],
    "cerveza": ["embriaguez", "alcohol", "sangre", "385"],
    "cinturon": ["seguridad", "utilice", "392", "390"],
    "pito": ["bocina", "sonoros", "ruidos", "392"],
    "bocina": ["sonoros", "ruidos", "392"],
    "llantas": ["lisas", "mal", "estado", "383"],
    "lisas": ["llantas", "estado", "383"],
    "botiquin": ["primeros", "auxilios", "extintor", "391"],
    "extintor": ["botiquin", "incendios", "391"],
    "velocidad": ["exceda", "limites", "rango", "moderado", "386", "389"],
    "correr": ["velocidad", "exceda", "limites", "386", "389"],
    "casco": ["motocicletas", "homologados", "retroreflectivas", "389"],
    "moto": ["motocicletas", "casco", "capacidad", "389", "390"],
    "placas": ["identificacion", "ocultas", "alteradas", "389"],
    "placa": ["placas", "identificacion", "ocultas", "389"],
    "polarizado": ["vidrios", "peliculas", "antisolares", "oscuras", "391"],
    "polarizados": ["vidrios", "peliculas", "antisolares", "oscuras", "391"],
    "acera": ["peaton", "aceras", "seguridad", "392"],
    "peaton": ["aceras", "sitios", "seguridad", "392", "373"],
    "ciclovia": ["ciclistas", "exclusivo", "invada", "390"],
    "ciclista": ["ciclistas", "preferente", "ciclovias", "390", "392"],
    "bicicleta": ["ciclistas", "transporte", "390"],
    "niños": ["solos", "supervision", "interior", "seguridades", "390", "391"],
    "bebe": ["niños", "seguridades", "solos", "390", "391"],
    "ambulancia": ["emergencia", "sirena", "alarma", "libre", "390", "392"],
    "sirena": ["emergencia", "alarma", "libre", "390", "391", "392"],
    "basura": ["desechos", "contaminen", "arroje", "recipientes", "392"],
    "caducada": ["licencia", "anulada", "revocada", "suspendida", "387"],
    "olvidar": ["portar", "licencia", "391"],
    "olvide": ["portar", "licencia", "391"],
    "portar": ["licencia", "391"],
    "peaje": ["peajes", "evadir", "390"],
    "puertas": ["abiertas", "urbano", "391"],
    "taximetro": ["taxi", "veinticuatro", "390"],
    "balde": ["baldes", "estribos", "pisaderas", "camionetas", "388"],
    "estribos": ["pisaderas", "baldes", "carrocerias", "388"],
}

# Patrones fuera de alcance o que requieren derivación administrativa a la ANT
PATRONES_DERIVACION_O_ABSTENCION = [
    r"hace\s+\d+\s+a[ñn]os",
    r"prescrib",
    r"prescripci[oó]n",
    r"exoner",
    r"amnist[ií]a",
    r"convenio\s+de\s+pago",
    r"impugn",
    r"apelaci[oó]n",
    r"juez\s+de\s+tr[aá]nsito",
    r"sistema\s+inform[aá]tico\s+de\s+la\s+ant",
    r"turno\s+en\s+la\s+ant",
    r"cu[aá]ntos\s+puntos\s+me\s+quedan\s+en\s+mi\s+c[eé]dula",
    r"consultar\s+mis\s+multas\s+por\s+placa",
    r"d[eé]cimo\s+tercer",
    r"impuesto\s+a\s+la\s+renta",
    r"receta\s+de",
    r"dengue",
    r"cacao",
    r"divorcio",
    r"liquidaci[oó]n\s+laboral",
]


@dataclass(frozen=True)
class FragmentoRAG:
    id: str
    texto: str
    metadatos: dict[str, str]
    puntaje: float


@dataclass(frozen=True)
class RespuestaRAG:
    consulta: str
    abstencion: bool
    mensaje_abstencion: str | None
    fragmentos: list[FragmentoRAG]
    cita_principal: str | None


def normalizar(texto: str) -> str:
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"[^a-z0-9\s\.]", " ", sin_tildes)


def tokenizar(texto: str) -> list[str]:
    norm = normalizar(texto)
    return [t for t in norm.split() if len(t) >= 2 and t not in VACIAS]


@lru_cache
def cargar_indice() -> list[dict]:
    if not RUTA_INDICE.exists():
        from scripts.ingest import construir_indice
        construir_indice()
    datos = json.loads(RUTA_INDICE.read_text(encoding="utf-8"))
    return datos.get("fragmentos", [])


def _cumple_filtro(metadatos: dict[str, str], where: dict[str, str] | None) -> bool:
    if not where:
        return True
    for k, v in where.items():
        if v is None or v == "":
            continue
        if str(metadatos.get(k, "")).lower() != str(v).lower():
            return False
    return True


def _detectar_abstencion(consulta: str) -> bool:
    c_norm = normalizar(consulta)
    for pat in PATRONES_DERIVACION_O_ABSTENCION:
        if re.search(pat, consulta.lower()) or re.search(pat, c_norm):
            return True
    return False


def recuperar(
    consulta: str,
    top_k: int = 5,
    where: dict[str, str] | None = None,
) -> RespuestaRAG:
    """Recupera los `top_k` artículos más relevantes aplicando primero el filtro `where`."""
    if _detectar_abstencion(consulta):
        return RespuestaRAG(
            consulta=consulta,
            abstencion=True,
            mensaje_abstencion=MENSAJE_ABSTENCION_RAG,
            fragmentos=[],
            cita_principal=None,
        )

    filtro_efectivo = {"vigente": "true", **(where or {})}
    candidatos = [f for f in cargar_indice() if _cumple_filtro(f["metadatos"], filtro_efectivo)]

    tokens_base = tokenizar(consulta)
    tokens_expandidos = list(tokens_base)
    for t in tokens_base:
        if t in TESAURO_VIAL:
            tokens_expandidos.extend(TESAURO_VIAL[t])

    # Coincidencia literal de número de artículo si el usuario menciona "Art. 389" o "389"
    arts_mencionados = set(re.findall(r"\b(3[789]\d|\d{1,3})\b", consulta))

    # Cálculo IDF sobre candidatos filtrados
    n_docs = max(1, len(candidatos))
    df: dict[str, int] = {}
    docs_tokens: list[set[str]] = []
    for f in candidatos:
        tset = set(tokenizar(f["texto"]))
        docs_tokens.append(tset)
        for tok in set(tokens_expandidos):
            if tok in tset:
                df[tok] = df.get(tok, 0) + 1

    puntuados: list[FragmentoRAG] = []
    for f, tset in zip(candidatos, docs_tokens):
        meta = f["metadatos"]
        art = meta.get("articulo", "")
        doc = meta.get("documento", "")
        puntaje = 0.0

        # 1. Impulso por coincidencia literal de artículo
        if art in arts_mencionados:
            puntaje += 18.0
        for tok in tokens_expandidos:
            if tok == art:
                puntaje += 10.0

        # 2. Puntaje léxico ponderado por IDF
        for tok in tokens_expandidos:
            if tok in tset:
                idf = math.log(1.0 + (n_docs - df.get(tok, 0) + 0.5) / (df.get(tok, 0) + 0.5))
                peso_original = 2.2 if tok in tokens_base else 1.1
                puntaje += idf * peso_original

        # 3. Prioridad normativa: el COIP prevalece para sanciones, puntos y contravenciones
        if doc == "COIP" and puntaje > 0:
            puntaje *= 1.45

        if puntaje > 0:
            puntuados.append(FragmentoRAG(id=f["id"], texto=f["texto"], metadatos=meta, puntaje=round(puntaje, 3)))

    puntuados.sort(key=lambda x: x.puntaje, reverse=True)
    mejores = puntuados[:top_k]

    # Regla de silencio: si ningún artículo alcanza el umbral mínimo de relevancia, se abstiene
    if not mejores or mejores[0].puntaje < 2.2:
        return RespuestaRAG(
            consulta=consulta,
            abstencion=True,
            mensaje_abstencion=MENSAJE_ABSTENCION_RAG,
            fragmentos=[],
            cita_principal=None,
        )

    top = mejores[0]
    cita = f"{top.metadatos['documento']}, Art. {top.metadatos['articulo']}"
    return RespuestaRAG(
        consulta=consulta,
        abstencion=False,
        mensaje_abstencion=None,
        fragmentos=mejores,
        cita_principal=cita,
    )
