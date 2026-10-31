from __future__ import annotations

from app.parametros import cargar_parametros
from app.schemas import Contravencion, ContravencionPublica, EscenarioVialSchema, ResultadoEvaluacion
from app.tools.calcular_sancion import calcular_sancion


def evaluar_respuesta(
    esc: EscenarioVialSchema,
    contravencion: Contravencion,
    respuesta: str,
    parametros: dict | None = None,
) -> ResultadoEvaluacion:
    p = parametros or cargar_parametros()
    return ResultadoEvaluacion(
        id_escenario=esc.id_escenario,
        respuesta_usuario=respuesta,
        es_correcta=respuesta == esc.respuesta_correcta,
        respuesta_correcta=esc.respuesta_correcta,
        explicacion_educativa=esc.explicacion_educativa,
        contravencion=ContravencionPublica(
            **contravencion.model_dump(
                include={
                    "id_contravencion",
                    "codigo_csv",
                    "clase",
                    "articulo",
                    "norma",
                    "descripcion_infraccion",
                    "texto_literal_coip",
                }
            )
        ),
        sancion=calcular_sancion(contravencion, p),
        aviso=p["aviso_educativo"],
    )
