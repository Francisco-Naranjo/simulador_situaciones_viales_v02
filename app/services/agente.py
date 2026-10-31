from __future__ import annotations

import re
from typing import Any

from app.parametros import cargar_parametros
from app.services.rag import (
    UMBRAL_DISTANCIA_COSENO,
    buscar_contravencion_relacionada,
    es_consulta_disputa,
    normalizar,
    responder,
)
from app.tools.calcular_sancion import calcular_sancion

TOPE_VUELTAS = 6
UMBRAL_CONFIANZA_AUTOMATICA = 0.80

HERRAMIENTAS_PERMITIDAS = [
    "buscar_normativa_rag",
    "identificar_contravencion_coip",
    "calcular_sancion",
    "verificar_cita_y_seguridad",
    "registrar_progreso",
    "ajustar_dificultad",
]

HERRAMIENTAS_FUERA_DE_ALCANCE = {
    "anular_boleta_ant": [
        r"\bborra(?:r)?\b.*\b(?:multa|boleta|citaci[oó]n)",
        r"\banula(?:r)?\b.*\b(?:multa|boleta|citaci[oó]n)",
        r"\belimina(?:r)?\b.*\b(?:multa|boleta|puntos)",
    ],
    "evadir_control_vial": [
        r"\bevadir\b.*\b(?:radar|fotorradar|control|agente|multa)",
        r"\btruco\b.*\b(?:alcohotector|radar|multa)",
        r"\bcomo\s+no\s+pagar\b",
    ],
    "modificar_sbu_oficial": [
        r"\bcambia(?:r)?\s+el\s+sbu\b",
        r"\bmodifica(?:r)?\s+la\s+ley\b",
    ],
}


def _detectar_herramienta_prohibida(pregunta: str) -> str | None:
    q_norm = normalizar(pregunta)
    for nombre_tool, patrones in HERRAMIENTAS_FUERA_DE_ALCANCE.items():
        for pat in patrones:
            if re.search(pat, pregunta.lower()) or re.search(pat, q_norm):
                return nombre_tool
    return None


def ejecutar_agente_consulta(
    pregunta: str,
    fragmentos_extra: list[dict] | None = None,
    simular_fallo_herramienta: bool = False,
) -> dict[str, Any]:
    bitacora: list[dict[str, str]] = []
    estaciones: list[dict[str, Any]] = []
    vueltas = 0
    parametros = cargar_parametros()

    if simular_fallo_herramienta:
        while vueltas < TOPE_VUELTAS:
            vueltas += 1
            bitacora.append({
                "vuelta": str(vueltas),
                "fase": "Observar -> Pensar -> Actuar -> Verificar",
                "herramienta": "buscar_normativa_rag",
                "detalle": f"Intento {vueltas}/{TOPE_VUELTAS}: la herramienta devolvió error transitorio.",
            })
        return {
            "pregunta": pregunta,
            "respuesta": (
                f"No logré completar la tarea en {TOPE_VUELTAS} pasos (tope de seguridad alcanzado). "
                "El agente se detuvo automáticamente para evitar un bucle infinito y solicita revisión humana."
            ),
            "tipo": "tope_vueltas_alcanzado",
            "abstencion": True,
            "citas": [],
            "cita_verificada": False,
            "mejor_distancia": 1.0,
            "resumen_clase": f"Grupo 8: tope de seguridad alcanzado ({TOPE_VUELTAS}/{TOPE_VUELTAS} vueltas) -> STOP",
            "sancion_calculada": None,
            "documento_envenenado": False,
            "alerta_seguridad": f"Freno de seguridad activado al alcanzar {TOPE_VUELTAS} vueltas.",
            "fragmentos": [],
            "agente": {
                "vueltas_usadas": vueltas,
                "tope_vueltas": TOPE_VUELTAS,
                "herramientas_permitidas": HERRAMIENTAS_PERMITIDAS,
                "herramientas_fuera_de_alcance": list(HERRAMIENTAS_FUERA_DE_ALCANCE.keys()),
                "herramienta_bloqueada": None,
                "bitacora": bitacora,
            },
            "automatizacion": {
                "modo": "revision_humana",
                "confianza": 0.0,
                "estaciones": estaciones,
            },
            "aviso": parametros["aviso_educativo"],
        }

    tool_prohibida = _detectar_herramienta_prohibida(pregunta)
    if tool_prohibida:
        vueltas = 1
        bitacora.append({
            "vuelta": "1",
            "fase": "Observar -> Pensar",
            "herramienta": tool_prohibida,
            "detalle": (
                f"El usuario solicita una acción que requeriría `{tool_prohibida}()`, "
                "la cual NO está en la lista cerrada de herramientas permitidas. Se rechaza en código."
            ),
        })
        estaciones = [
            {"estacion": "1 · Clasificar", "actor": "IA", "resultado": "accion_fuera_de_alcance", "confianza": 0.98},
            {"estacion": "2 · Extraer datos", "actor": "IA", "resultado": f'{{"herramienta_solicitada": "{tool_prohibida}"}}'},
            {"estacion": "3 · Reglas (código)", "actor": "código", "resultado": f"{tool_prohibida} not in HERRAMIENTAS_PERMITIDAS -> BLOQUEAR"},
            {"estacion": "4 · Actuar", "actor": "sistema", "resultado": "Rechazo seguro y oferta de orientación normativa legal"},
        ]
        return {
            "pregunta": pregunta,
            "respuesta": (
                f"No tengo permiso ni herramienta para ejecutar `{tool_prohibida}`. "
                "Vía Segura es un simulador educativo de alcance controlado: puedo buscar el artículo del COIP "
                "y calcular de forma referencial la multa legal, pero nunca anular boletas ni sugerir cómo evadir controles."
            ),
            "tipo": "fuera_de_alcance_herramienta",
            "abstencion": True,
            "citas": [],
            "cita_verificada": True,
            "mejor_distancia": 1.0,
            "resumen_clase": f"Grupo 8: herramienta `{tool_prohibida}` fuera de alcance -> RECHAZADA en código",
            "sancion_calculada": None,
            "documento_envenenado": False,
            "alerta_seguridad": f"Alcance controlado: `{tool_prohibida}` no pertenece a HERRAMIENTAS_PERMITIDAS.",
            "fragmentos": [],
            "agente": {
                "vueltas_usadas": vueltas,
                "tope_vueltas": TOPE_VUELTAS,
                "herramientas_permitidas": HERRAMIENTAS_PERMITIDAS,
                "herramientas_fuera_de_alcance": list(HERRAMIENTAS_FUERA_DE_ALCANCE.keys()),
                "herramienta_bloqueada": tool_prohibida,
                "bitacora": bitacora,
            },
            "automatizacion": {
                "modo": "rechazo_alcance_controlado",
                "confianza": 0.98,
                "estaciones": estaciones,
            },
            "aviso": parametros["aviso_educativo"],
        }

    vueltas += 1
    res = responder(pregunta, fragmentos_extra=fragmentos_extra)
    n_frags = len(res["fragmentos"])
    mejor_art = res["fragmentos"][0]["articulo"] if n_frags > 0 else "ninguno"
    bitacora.append({
        "vuelta": str(vueltas),
        "fase": "Observar -> Pensar -> Actuar -> Verificar",
        "herramienta": "buscar_normativa_rag",
        "detalle": (
            f"Consulta en ChromaDB (`where={{'vigente': True}}`, top_k=5): "
            f"{n_frags} fragmentos recuperados; mejor artículo={mejor_art} "
            f"(distancia coseno={res['mejor_distancia']:.2f})."
        ),
    })

    if not res["abstencion"] and vueltas < TOPE_VUELTAS:
        vueltas += 1
        contrav = buscar_contravencion_relacionada(pregunta, mejor_art)
        if contrav is not None:
            sancion = calcular_sancion(contrav)
            bitacora.append({
                "vuelta": str(vueltas),
                "fase": "Pensar -> Actuar -> Verificar",
                "herramienta": "calcular_sancion",
                "detalle": (
                    f"Contravención `{contrav.id_contravencion}` ({contrav.porcentaje_sbu:g}% SBU): "
                    f"multa=${sancion.multa_usd:.2f} USD (SBU=${sancion.sbu_usd:.2f}), "
                    f"puntos COIP={sancion.puntos_reducidos:g}."
                ),
            })
        else:
            bitacora.append({
                "vuelta": str(vueltas),
                "fase": "Pensar -> Actuar -> Verificar",
                "herramienta": "identificar_contravencion_coip",
                "detalle": "Consulta normativa general o reglamentaria sin multa pecuniaria directa.",
            })

    if vueltas < TOPE_VUELTAS:
        vueltas += 1
        bitacora.append({
            "vuelta": str(vueltas),
            "fase": "Verificar (Cierre del bucle)",
            "herramienta": "verificar_cita_y_seguridad",
            "detalle": f"Cita verificada={res['cita_verificada']}; documento_envenenado={res['documento_envenenado']}.",
        })

    confianza = round(max(0.35, min(0.98, 1.0 - res["mejor_distancia"])), 2)
    es_disputa = es_consulta_disputa(pregunta)
    modo_auto = "automatico" if (not res["abstencion"] and confianza >= UMBRAL_CONFIANZA_AUTOMATICA and not es_disputa) else "revision_humana_o_derivacion"

    estaciones = [
        {
            "estacion": "1 · Clasificar",
            "actor": "IA",
            "resultado": res["tipo"],
            "confianza": confianza,
        },
        {
            "estacion": "2 · Extraer datos",
            "actor": "IA",
            "resultado": json_resumen_extraccion(mejor_art, res["sancion_calculada"]),
        },
        {
            "estacion": "3 · Reglas (código)",
            "actor": "código",
            "resultado": (
                f"distancia {res['mejor_distancia']:.2f} <= {UMBRAL_DISTANCIA_COSENO} y SBU=${parametros['sbu_usd']:.2f} -> responder con cita"
                if not res["abstencion"]
                else "baja similitud o caso en disputa -> desviar a orientación humana / ANT"
            ),
        },
        {
            "estacion": "4 · Actuar",
            "actor": "sistema",
            "resultado": (
                f"Respuesta fundamentada con cita {res['citas']}"
                if not res["abstencion"]
                else "Silencio / derivación a autoridad competente (ANT / consultorio jurídico)"
            ),
        },
    ]

    return {
        **res,
        "agente": {
            "vueltas_usadas": vueltas,
            "tope_vueltas": TOPE_VUELTAS,
            "herramientas_permitidas": HERRAMIENTAS_PERMITIDAS,
            "herramientas_fuera_de_alcance": list(HERRAMIENTAS_FUERA_DE_ALCANCE.keys()),
            "herramienta_bloqueada": None,
            "bitacora": bitacora,
        },
        "automatizacion": {
            "modo": modo_auto,
            "confianza": confianza,
            "estaciones": estaciones,
        },
        "aviso": parametros["aviso_educativo"],
    }


def json_resumen_extraccion(articulo: str, sancion: dict[str, Any] | None) -> str:
    if sancion:
        return (
            f'{{"articulo": "Art. {articulo}", "codigo": "{sancion["codigo_csv"]}", '
            f'"porcentaje_sbu": {sancion["porcentaje_sbu"]}, "multa_usd": {sancion["multa_usd"]}}}'
        )
    return f'{{"articulo_detectado": "{articulo}"}}'
