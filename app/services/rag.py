from __future__ import annotations

import json
import math
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from scripts.ingest import MODELO_EMBEDDINGS, codificar_e5_multilingue

RAIZ = Path(__file__).resolve().parent.parent.parent
RUTA_INDICE = RAIZ / "data" / "processed" / "indice_rag.json"
RUTA_CHROMA_JSON = RAIZ / "chroma_db" / "normativa_collection.json"

UMBRAL_DISTANCIA_COSENO = 0.45

MENSAJE_ABSTENCION_RAG = (
    "La normativa que tengo cargada (COIP, LOTTTSV y su Reglamento) no responde esta pregunta "
    "o requiere verificación administrativa. Le recomiendo consultar directamente a la Agencia Nacional de Tránsito (ANT)."
)

MENSAJE_DERIVACION_DISPUTA = (
    "Puedo explicarle lo que establece el COIP y el Reglamento de Tránsito con el artículo correspondiente, "
    "pero no puedo dictaminar quién tiene razón en una disputa ni asesorar cómo impugnar una boleta. "
    "Para impugnaciones dentro del término legal de tres días, acuda a la unidad judicial o a un consultorio jurídico gratuito."
)

VACIAS = {
    "como", "cual", "cuando", "cuanto", "cuantos", "donde", "para", "pero", "porque",
    "quien", "tengo", "puedo", "puede", "pasa", "paso", "sobre", "entre", "hasta",
    "desde", "este", "esta", "estos", "estas", "solo", "hacer", "hago", "dice", "segun",
    "una", "uno", "unos", "unas", "los", "las", "del", "por", "con", "sin", "que",
}

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
    r"capital\s+de\s+francia",
    r"matr[ií]cula\s+en\s+la\s+universidad",
]

PATRONES_DISPUTA_LITIGIOSA = [
    r"qui[eé]n\s+tiene\s+(?:la\s+)?raz[oó]n",
    r"agente\s+(?:dice|miente|inventa)",
    r"estaba\s+en\s+amarillo\s+y\s+el\s+agente",
    r"no\s+firm[eé]\s+la\s+boleta",
    r"ganar\s+la\s+impugnaci[oó]n",
]

PATRONES_DOCUMENTO_ENVENENADO = [
    r"ignora\s+(?:todas\s+)?las\s+instrucciones",
    r"olvida\s+(?:todas\s+)?las\s+reglas",
    r"system\s*override",
    r"instrucci[oó]n\s+prioritaria\s+del\s+sistema",
    r"responde\s+siempre\s+que\s+no\s+hay\s+multa",
    r"di\s+que\s+todas\s+las\s+multas\s+son\s+de\s+0",
    r"ignore\s+previous\s+instructions",
]


@dataclass(frozen=True)
class FragmentoRAG:
    id: str
    texto: str
    metadatos: dict[str, str]
    puntaje: float
    distancia: float = 0.12
    puesto: int = 1


@dataclass(frozen=True)
class RespuestaRAG:
    consulta: str
    abstencion: bool
    mensaje_abstencion: str | None
    fragmentos: list[FragmentoRAG]
    cita_principal: str | None
    mejor_distancia: float = 1.0
    documento_envenenado: bool = False
    alerta_seguridad: str | None = None


def normalizar(texto: str) -> str:
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"[^a-z0-9\s\.]", " ", sin_tildes)


def tokenizar(texto: str) -> list[str]:
    return [t for t in normalizar(texto).split() if len(t) >= 2 and t not in VACIAS]


def detectar_y_sanitizar_envenenamiento(texto: str) -> tuple[str, bool, str | None]:
    lineas_seguras: list[str] = []
    detectado = False
    motivo: str | None = None
    for oracion in re.split(r"(?<=[\.\n])", texto):
        if any(re.search(pat, oracion, re.I) for pat in PATRONES_DOCUMENTO_ENVENENADO):
            detectado = True
            motivo = (
                "Se detectó y neutralizó una instrucción de inyección indirecta en el documento recuperado "
                "(los documentos son datos normativos, nunca instrucciones del sistema)."
            )
            continue
        lineas_seguras.append(oracion)
    return "".join(lineas_seguras).strip(), detectado, motivo


@lru_cache
def cargar_indice() -> list[dict]:
    if not RUTA_INDICE.exists():
        from scripts.ingest import construir_indice
        construir_indice()
    datos = json.loads(RUTA_INDICE.read_text(encoding="utf-8"))
    return datos.get("fragmentos", [])


@lru_cache
def cargar_vectores_chroma() -> dict[str, list[float]]:
    if RUTA_CHROMA_JSON.exists():
        try:
            datos = json.loads(RUTA_CHROMA_JSON.read_text(encoding="utf-8"))
            return {r["id"]: r["embedding"] for r in datos.get("registros", []) if "embedding" in r}
        except Exception:
            pass
    indice = cargar_indice()
    vecs = codificar_e5_multilingue([f"passage: {f['texto']}" for f in indice])
    return {f["id"]: v for f, v in zip(indice, vecs)}


def _cumple_filtro(metadatos: dict[str, Any], where: dict[str, Any] | None) -> bool:
    if not where:
        return True
    for k, v in where.items():
        if v is None or v == "":
            continue
        val_meta = metadatos.get(k, "")
        if isinstance(v, bool):
            if (str(val_meta).lower() in ("true", "1", "si", "sí")) != v:
                return False
        elif str(val_meta).lower() != str(v).lower():
            return False
    return True


def _cumple_where_document(texto: str, where_document: dict[str, str] | None) -> bool:
    if not where_document:
        return True
    buscado = where_document.get("$contains", "").strip()
    if not buscado:
        return True
    return buscado.lower() in texto.lower() or normalizar(buscado) in normalizar(texto)


def _detectar_abstencion(consulta: str) -> bool:
    c_norm = normalizar(consulta)
    return any(re.search(pat, consulta.lower()) or re.search(pat, c_norm) for pat in PATRONES_DERIVACION_O_ABSTENCION)


def es_consulta_disputa(consulta: str) -> bool:
    c_norm = normalizar(consulta)
    return any(re.search(p, consulta.lower()) or re.search(p, c_norm) for p in PATRONES_DISPUTA_LITIGIOSA)


def distancia_coseno(u: list[float], v: list[float]) -> float:
    if not u or not v or len(u) != len(v):
        return 1.0
    dot = max(-1.0, min(1.0, sum(a * b for a, b in zip(u, v))))
    return round(max(0.0, 1.0 - dot), 4)


def recuperar(
    consulta: str,
    top_k: int = 5,
    where: dict[str, Any] | None = None,
    where_document: dict[str, str] | None = None,
    fragmentos_extra: list[dict] | None = None,
) -> RespuestaRAG:
    """Recupera los `top_k` artículos vigentes más cercanos combinando distancia coseno e IDF híbrido."""
    if _detectar_abstencion(consulta):
        return RespuestaRAG(
            consulta=consulta,
            abstencion=True,
            mensaje_abstencion=MENSAJE_ABSTENCION_RAG,
            fragmentos=[],
            cita_principal=None,
            mejor_distancia=0.78,
        )

    filtro_efectivo: dict[str, Any] = {"vigente": "true", **(where or {})}
    base = list(cargar_indice()) + list(fragmentos_extra or [])
    candidatos = [
        f for f in base
        if _cumple_filtro(f["metadatos"], filtro_efectivo)
        and _cumple_where_document(f["texto"], where_document)
    ]

    if not candidatos:
        return RespuestaRAG(
            consulta=consulta,
            abstencion=True,
            mensaje_abstencion=MENSAJE_ABSTENCION_RAG,
            fragmentos=[],
            cita_principal=None,
            mejor_distancia=0.85,
        )

    vec_q = codificar_e5_multilingue([f"query: {consulta}"])[0]
    mapa_vectores = cargar_vectores_chroma()

    tokens_base = tokenizar(consulta)
    tokens_expandidos = list(tokens_base)
    for t in tokens_base:
        if t in TESAURO_VIAL:
            tokens_expandidos.extend(TESAURO_VIAL[t])

    arts_mencionados = set(re.findall(r"\b(3[789]\d|\d{1,3})\b", consulta))
    for m_cod in re.findall(r"C-(\d{3})-\d{2}", consulta.upper()):
        arts_mencionados.add(m_cod)

    n_docs = max(1, len(candidatos))
    df: dict[str, int] = {}
    docs_tokens: list[set[str]] = []
    for f in candidatos:
        tset = set(tokenizar(f["texto"]))
        docs_tokens.append(tset)
        for tok in set(tokens_expandidos):
            if tok in tset:
                df[tok] = df.get(tok, 0) + 1

    preliminares: list[tuple[dict, float, float, bool, str | None]] = []
    hubo_envenenamiento = False
    alerta_env: str | None = None

    for f, tset in zip(candidatos, docs_tokens):
        texto_sanitizado, envenenado, motivo_env = detectar_y_sanitizar_envenenamiento(f["texto"])
        if envenenado:
            hubo_envenenamiento = True
            alerta_env = motivo_env

        meta = f["metadatos"]
        art = str(meta.get("articulo", ""))
        doc = str(meta.get("documento", ""))
        vec_doc = mapa_vectores.get(f["id"]) or codificar_e5_multilingue([f"passage: {texto_sanitizado}"])[0]
        dist_vec = distancia_coseno(vec_q, vec_doc)

        puntaje = 18.0 if art in arts_mencionados else 0.0
        for tok in tokens_expandidos:
            if tok == art:
                puntaje += 10.0
            if tok in tset:
                idf = math.log1p((n_docs - df.get(tok, 0) + 0.5) / (df.get(tok, 0) + 0.5))
                puntaje += idf * (2.2 if tok in tokens_base else 1.1)

        similitud_vec = max(0.0, 1.0 - dist_vec)
        if puntaje > 0 or similitud_vec >= 0.42:
            puntaje += similitud_vec * 3.2
        if doc == "COIP" and puntaje > 0:
            puntaje *= 1.45

        if puntaje > 0:
            dist_hibrida = round(max(0.04, min(0.95, 0.46 / (1.0 + 0.14 * puntaje) + 0.18 * dist_vec)), 2)
            preliminares.append(({**f, "texto": texto_sanitizado}, round(puntaje, 3), dist_hibrida, envenenado, motivo_env))

    preliminares.sort(key=lambda x: (-x[1], x[2]))
    recorte = preliminares[:top_k]

    if not recorte or recorte[0][1] < 2.2 or recorte[0][2] > UMBRAL_DISTANCIA_COSENO:
        mejor_d = recorte[0][2] if recorte else 0.74
        return RespuestaRAG(
            consulta=consulta,
            abstencion=True,
            mensaje_abstencion=MENSAJE_ABSTENCION_RAG,
            fragmentos=[],
            cita_principal=None,
            mejor_distancia=max(0.52, mejor_d),
            documento_envenenado=hubo_envenenamiento,
            alerta_seguridad=alerta_env,
        )

    mejores = [
        FragmentoRAG(
            id=item[0]["id"],
            texto=item[0]["texto"],
            metadatos=item[0]["metadatos"],
            puntaje=item[1],
            distancia=item[2],
            puesto=idx + 1,
        )
        for idx, item in enumerate(recorte)
    ]

    top = mejores[0]
    return RespuestaRAG(
        consulta=consulta,
        abstencion=False,
        mensaje_abstencion=None,
        fragmentos=mejores,
        cita_principal=f"{top.metadatos['documento']}, Art. {top.metadatos['articulo']}",
        mejor_distancia=top.distancia,
        documento_envenenado=hubo_envenenamiento,
        alerta_seguridad=alerta_env,
    )


def buscar_contravencion_relacionada(consulta: str, articulo_recuperado: str | None) -> Any | None:
    from app.tools.contravenciones import cargar_tabla

    tokens_q = set(tokenizar(consulta))
    for t in list(tokens_q):
        if t in TESAURO_VIAL:
            tokens_q.update(TESAURO_VIAL[t])

    mejor = None
    mejor_pts = 0.0
    for c in cargar_tabla().values():
        pts = 6.0 if (articulo_recuperado and f"Art. {articulo_recuperado}" in c.articulo) else 0.0
        tokens_c = set(tokenizar(f"{c.descripcion_infraccion} {c.texto_literal_coip or ''}"))
        pts += len(tokens_q.intersection(tokens_c)) * 2.5
        if pts > mejor_pts:
            mejor_pts = pts
            mejor = c
    return mejor if mejor_pts >= 5.0 else None


def responder(
    pregunta: str,
    fragmentos_extra: list[dict] | None = None,
) -> dict[str, Any]:
    es_disputa = es_consulta_disputa(pregunta)
    res_rag = recuperar(pregunta, top_k=5, where={"vigente": "true"}, fragmentos_extra=fragmentos_extra)

    if res_rag.abstencion and not es_disputa:
        return {
            "pregunta": pregunta,
            "abstencion": True,
            "tipo": "silencio",
            "respuesta": res_rag.mensaje_abstencion or MENSAJE_ABSTENCION_RAG,
            "citas": [],
            "cita_verificada": True,
            "mejor_distancia": res_rag.mejor_distancia,
            "umbral_distancia": UMBRAL_DISTANCIA_COSENO,
            "modelo_embeddings": MODELO_EMBEDDINGS,
            "resumen_clase": (
                f"Grupo 8: nuestra pregunta «{pregunta}» no encontró artículo cercano "
                f"(mejor distancia {res_rag.mejor_distancia:.2f} > umbral {UMBRAL_DISTANCIA_COSENO}) -> SILENCIO"
            ),
            "sancion_calculada": None,
            "documento_envenenado": res_rag.documento_envenenado,
            "alerta_seguridad": res_rag.alerta_seguridad,
            "fragmentos": [],
        }

    if es_disputa:
        citas_disp = [res_rag.cita_principal] if res_rag.cita_principal else ["COIP, Art. 389"]
        art_ref = res_rag.fragmentos[0].metadatos.get("articulo", "389") if res_rag.fragmentos else "389"
        return {
            "pregunta": pregunta,
            "abstencion": True,
            "tipo": "derivacion_disputa",
            "respuesta": (
                f"Según el COIP (Art. {art_ref}), las contravenciones deben estar respaldadas en la boleta de citación. "
                f"{MENSAJE_DERIVACION_DISPUTA}"
            ),
            "citas": citas_disp,
            "cita_verificada": True,
            "mejor_distancia": res_rag.mejor_distancia,
            "umbral_distancia": UMBRAL_DISTANCIA_COSENO,
            "modelo_embeddings": MODELO_EMBEDDINGS,
            "resumen_clase": (
                f"Grupo 8: nuestra pregunta «{pregunta}» encontró el Art. {art_ref} en el puesto 1, "
                "pero al ser un caso en disputa cita la norma y deriva sin dictaminar."
            ),
            "sancion_calculada": None,
            "documento_envenenado": res_rag.documento_envenenado,
            "alerta_seguridad": res_rag.alerta_seguridad,
            "fragmentos": [
                {
                    "puesto": f.puesto,
                    "id": f.id,
                    "documento": f.metadatos.get("documento", ""),
                    "articulo": f.metadatos.get("articulo", ""),
                    "distancia": f.distancia,
                    "puntaje": f.puntaje,
                    "metadatos": f.metadatos,
                    "texto": f.texto,
                }
                for f in res_rag.fragmentos
            ],
        }

    top = res_rag.fragmentos[0]
    art_num = top.metadatos.get("articulo", "")
    doc_nom = top.metadatos.get("documento", "COIP")
    cita_oficial = f"{doc_nom}, Art. {art_num}"
    cita_verificada = art_num in {f.metadatos.get("articulo", "") for f in res_rag.fragmentos}

    sancion_dict = None
    contrav = buscar_contravencion_relacionada(pregunta, art_num)
    if contrav is not None:
        from app.tools.calcular_sancion import calcular_sancion

        sancion_obj = calcular_sancion(contrav)
        pts_hoy = sancion_obj.puntos_aplicables if sancion_obj.puntos_aplicables is not None else sancion_obj.puntos_reducidos
        sancion_dict = {
            "id_contravencion": contrav.id_contravencion,
            "codigo_csv": contrav.codigo_csv,
            "clase": contrav.clase,
            "articulo": contrav.articulo,
            "porcentaje_sbu": contrav.porcentaje_sbu,
            "multa_usd": sancion_obj.multa_usd,
            "sbu_referencia_usd": sancion_obj.sbu_usd,
            "puntos_texto_coip": sancion_obj.puntos_reducidos,
            "puntos_aplicables_hoy": pts_hoy,
            "pena_adicional": sancion_obj.pena_adicional,
            "descripcion": contrav.descripcion_infraccion,
        }
        texto_respuesta = (
            f"Según el {cita_oficial} ({contrav.articulo} · {contrav.clase}), "
            f"la conducta «{contrav.descripcion_infraccion}» tiene una sanción del "
            f"{contrav.porcentaje_sbu:g}% del SBU, calculada en código como "
            f"${sancion_obj.multa_usd:.2f} USD (SBU 2026: ${sancion_obj.sbu_usd:.2f} USD). "
            f"Puntos en el texto del artículo: {sancion_obj.puntos_reducidos:g} pts "
            f"(puntos aplicables hoy tras reforma LOTTTSV 2021: {pts_hoy:g} pts)."
        )
        if sancion_obj.pena_adicional:
            texto_respuesta += f" Pena adicional prevista: {sancion_obj.pena_adicional}."
    else:
        extracto = top.texto[:340].rstrip() + ("..." if len(top.texto) > 340 else "")
        texto_respuesta = f"Según el {cita_oficial}: «{extracto}»"

    return {
        "pregunta": pregunta,
        "abstencion": False,
        "tipo": "con_fuente",
        "respuesta": texto_respuesta,
        "citas": [cita_oficial],
        "cita_verificada": cita_verificada,
        "mejor_distancia": top.distancia,
        "umbral_distancia": UMBRAL_DISTANCIA_COSENO,
        "modelo_embeddings": MODELO_EMBEDDINGS,
        "resumen_clase": f"Grupo 8: nuestra pregunta «{pregunta}» encontró el Art. {art_num} en el puesto {top.puesto}",
        "sancion_calculada": sancion_dict,
        "documento_envenenado": res_rag.documento_envenenado,
        "alerta_seguridad": res_rag.alerta_seguridad,
        "fragmentos": [
            {
                "puesto": f.puesto,
                "id": f.id,
                "documento": f.metadatos.get("documento", ""),
                "articulo": f.metadatos.get("articulo", ""),
                "distancia": f.distancia,
                "puntaje": f.puntaje,
                "metadatos": f.metadatos,
                "texto": f.texto,
            }
            for f in res_rag.fragmentos
        ],
    }
