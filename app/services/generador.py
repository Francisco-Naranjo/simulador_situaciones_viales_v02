"""Generación de escenarios: construye el prompt, llama al modelo y valida la salida
contra la tabla canónica. Si el escenario no corresponde a la tabla, se DESCARTA y se
pide otro (hasta max_intentos_generacion); nunca se muestra un escenario inventado.
"""
from __future__ import annotations

import json
import uuid

from app.parametros import cargar_parametros
from app.schemas import Contravencion, EscenarioVialSchema, SolicitudEscenario
from app.services.llm import ClienteLLM, _registrar, cargar_prompt
from app.tools.contravenciones import EscenarioInvalido, candidatas, cargar_tabla, validar_escenario

PROMPT = "system_v3"  # versión ganadora de docs/05-prompts.md (actualizar si la comparación dice otra cosa)


def construir_mensaje(solicitud: SolicitudEscenario, opciones: list[Contravencion]) -> str:
    """Mensaje de usuario con DATOS delimitados. El texto del usuario (tema) va dentro de
    <solicitud> como JSON: es un dato, no una instrucción (mitigación de inyección, OWASP LLM01).
    A la tabla NO se le envían porcentajes ni puntos: el modelo no tiene con qué calcular."""
    tabla = [{"id_contravencion": c.id_contravencion, "articulo": c.articulo, "norma": c.norma,
              "descripcion_infraccion": c.descripcion_infraccion} for c in opciones]
    return (
        "<solicitud>\n" + json.dumps(solicitud.model_dump(), ensure_ascii=False) + "\n</solicitud>\n\n"
        "<contravenciones_permitidas>\n" + json.dumps(tabla, ensure_ascii=False, indent=1)
        + "\n</contravenciones_permitidas>"
    )


def generar_escenario(llm: ClienteLLM, solicitud: SolicitudEscenario,
                      prompt: str = PROMPT) -> tuple[EscenarioVialSchema, Contravencion]:
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
        except EscenarioInvalido as e:  # FueraDeDominio sube tal cual: es una abstención, no un fallo
            motivo = str(e)
            _registrar(evento="escenario_invalido", intento=intento, motivo=motivo, proveedor=r.proveedor)
            continue
        # El código dispone: id propio y artículo tomado de la tabla, no del texto del modelo.
        esc = esc.model_copy(update={"id_escenario": f"ESC-{uuid.uuid4().hex[:12]}",
                                     "articulo_norma": f"{c.articulo} · {c.norma}"})
        _registrar(evento="escenario_valido", intento=intento, contravencion=c.id_contravencion,
                   proveedor=r.proveedor, tokens_entrada=r.tokens_entrada, tokens_salida=r.tokens_salida,
                   latencia_ms=r.latencia_ms)
        return esc, c
    raise EscenarioInvalido(motivo)
