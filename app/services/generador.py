from __future__ import annotations

import json
import uuid

from app.parametros import cargar_parametros
from app.schemas import Contravencion, EscenarioVialSchema, SolicitudEscenario
from app.services.llm import ClienteLLM, _registrar, cargar_prompt
from app.services.rag import normalizar, recuperar
from app.tools.contravenciones import EscenarioInvalido, candidatas, cargar_tabla, validar_escenario

PROMPT = "system_v3"
MAX_CANDIDATAS_PROMPT = 18


def seleccionar_candidatas_rag(
    solicitud: SolicitudEscenario,
    opciones: list[Contravencion],
) -> tuple[list[Contravencion], list[dict]]:
    fragmentos_rag: list[dict] = []
    if not solicitud.tema or not solicitud.tema.strip():
        if len(opciones) <= MAX_CANDIDATAS_PROMPT:
            return opciones, fragmentos_rag
        paso = max(1, len(opciones) // MAX_CANDIDATAS_PROMPT)
        return opciones[::paso][:MAX_CANDIDATAS_PROMPT], fragmentos_rag

    res_rag = recuperar(solicitud.tema, top_k=3)
    arts_rag = {f.metadatos.get("articulo", "") for f in res_rag.fragmentos if f.metadatos.get("documento") == "COIP"}
    for f in res_rag.fragmentos[:2]:
        fragmentos_rag.append({
            "cita": f"{f.metadatos.get('documento')} Art. {f.metadatos.get('articulo')}",
            "clase": f.metadatos.get("clase", ""),
            "extracto": f.texto[:600],
        })

    palabras = [p for p in normalizar(solicitud.tema).split() if len(p) >= 4]
    puntuadas: list[tuple[int, Contravencion]] = []
    for c in opciones:
        pts = sum(25 for a in arts_rag if a and f"Art. {a}" in c.articulo)
        texto_c = normalizar(f"{c.descripcion_infraccion} {c.texto_literal_coip or ''} {c.articulo}")
        pts += sum(len(p) for p in palabras if p in texto_c)
        puntuadas.append((pts, c))

    puntuadas.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in puntuadas[:MAX_CANDIDATAS_PROMPT]], fragmentos_rag


def construir_mensaje(solicitud: SolicitudEscenario, opciones: list[Contravencion]) -> str:
    opciones_filtradas, fragmentos_rag = seleccionar_candidatas_rag(solicitud, opciones)
    tabla = [
        {
            "id_contravencion": c.id_contravencion,
            "articulo": c.articulo,
            "norma": c.norma,
            "descripcion_infraccion": c.descripcion_infraccion,
        }
        for c in opciones_filtradas
    ]
    partes = [
        "<solicitud>\n" + json.dumps(solicitud.model_dump(), ensure_ascii=False) + "\n</solicitud>",
        "<contravenciones_permitidas>\n" + json.dumps(tabla, ensure_ascii=False, indent=1) + "\n</contravenciones_permitidas>",
    ]
    if fragmentos_rag:
        partes.append(
            "<contexto_rag_normativo>\n" + json.dumps(fragmentos_rag, ensure_ascii=False, indent=1) + "\n</contexto_rag_normativo>"
        )
    return "\n\n".join(partes)


def generar_escenario(
    llm: ClienteLLM,
    solicitud: SolicitudEscenario,
    prompt: str = PROMPT,
) -> tuple[EscenarioVialSchema, Contravencion]:
    tabla = cargar_tabla()
    mensaje = construir_mensaje(solicitud, candidatas(solicitud.perfil, tabla))
    system = cargar_prompt(prompt)
    intentos = int(cargar_parametros().get("max_intentos_generacion", 2))
    motivo = ""
    for intento in range(1, intentos + 1):
        r = llm.generar_json(system, mensaje, EscenarioVialSchema)
        esc: EscenarioVialSchema = r.datos
        try:
            c = validar_escenario(esc, solicitud.perfil, solicitud.nivel_dificultad, tabla)
        except EscenarioInvalido as e:
            motivo = str(e)
            _registrar(evento="escenario_invalido", intento=intento, motivo=motivo, proveedor=r.proveedor)
            continue
        esc = esc.model_copy(
            update={
                "id_escenario": f"ESC-{uuid.uuid4().hex[:12]}",
                "articulo_norma": f"{c.articulo} · {c.norma}",
            }
        )
        _registrar(
            evento="escenario_valido",
            intento=intento,
            contravencion=c.id_contravencion,
            proveedor=r.proveedor,
            tokens_entrada=r.tokens_entrada,
            tokens_salida=r.tokens_salida,
            latencia_ms=r.latencia_ms,
        )
        return esc, c
    raise EscenarioInvalido(motivo)
