from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field

from app.parametros import cargar_parametros
from app.services.rag import (
    MENSAJE_ABSTENCION_RAG,
    MENSAJE_DERIVACION_DISPUTA,
    MODELO_EMBEDDINGS,
    UMBRAL_DISTANCIA_COSENO,
    buscar_contravencion_relacionada,
    detectar_y_sanitizar_envenenamiento,
    es_consulta_disputa,
    normalizar,
    recuperar,
)
from app.tools.calcular_sancion import calcular_sancion
from app.tools.contravenciones import cargar_tabla
from app.tools.progreso import ajustar_dificultad, registrar_progreso

TOPE_VUELTAS = 6
UMBRAL_CONFIANZA_AUTOMATICA = 0.80

SYSTEM_PROMPT_AGENTE = (
    "Eres el agente normativo de Vía Segura (Ecuador). "
    "Ante consultas viales debes invocar herramientas de la lista permitida mediante tool_calls: "
    "1) buscar_normativa_rag para recuperar artículos vigentes del COIP/LOTTTSV/Reglamento, "
    "2) identificar_contravencion_coip para asociar la conducta con el catálogo oficial, "
    "3) calcular_sancion para calcular multa exacta en código según el SBU vigente, y "
    "4) verificar_cita_y_seguridad antes de emitir la respuesta final."
)

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


class HerramientaNoPermitidaError(PermissionError):
    def __init__(self, nombre: str):
        self.nombre = nombre
        super().__init__(f"La herramienta '{nombre}' no pertenece a HERRAMIENTAS_PERMITIDAS.")


class ArgsBuscarNormativaRAG(BaseModel):
    model_config = ConfigDict(extra="forbid")
    consulta: str = Field(..., min_length=2, description="Consulta ciudadana sobre normativa vial ecuatoriana")
    top_k: int = Field(default=5, ge=1, le=10, description="Cantidad de fragmentos vigentes a recuperar")


class ArgsIdentificarContravencion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    consulta: str = Field(..., min_length=2, description="Conducta vial descrita por el usuario")
    articulo_recuperado: str | None = Field(default=None, description="Número de artículo recuperado (ej. 389)")


class ArgsCalcularSancion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id_contravencion: str = Field(..., min_length=3, description="ID canónico o código CSV de la contravención")


class ArgsVerificarCitaYSeguridad(BaseModel):
    model_config = ConfigDict(extra="forbid")
    articulo: str = Field(..., min_length=1, description="Artículo citado para verificar contra fragmentos")
    articulos_recuperados: list[str] = Field(default_factory=list, description="Lista de artículos en fragmentos")
    texto_fragmento: str = Field(default="", description="Texto del fragmento para sanitizar inyecciones")


class ArgsRegistrarProgreso(BaseModel):
    model_config = ConfigDict(extra="forbid")
    usuario_id: str = Field(default="anonimo", min_length=1)
    es_correcta: bool
    multa_usd: float = Field(default=0.0, ge=0.0)
    puntos_reducidos: float = Field(default=0.0, ge=0.0)


class ArgsAjustarDificultad(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ultimos_resultados: list[bool] = Field(default_factory=list)


@dataclass
class FuncionToolCall:
    name: str
    arguments: str


@dataclass
class LlamadaHerramienta:
    id: str
    function: FuncionToolCall
    type: str = "function"


@dataclass
class MensajeModelo:
    role: str = "assistant"
    content: str | None = None
    tool_calls: list[LlamadaHerramienta] | None = None


def _ejecutar_buscar_normativa_rag(args: ArgsBuscarNormativaRAG, ctx: dict[str, Any]) -> dict[str, Any]:
    res_rag = recuperar(
        args.consulta,
        top_k=args.top_k,
        where={"vigente": "true"},
        fragmentos_extra=ctx.get("fragmentos_extra"),
    )
    fragmentos_serializados = [
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
    ]
    salida = {
        "abstencion": res_rag.abstencion,
        "mensaje_abstencion": res_rag.mensaje_abstencion,
        "cita_principal": res_rag.cita_principal,
        "mejor_distancia": res_rag.mejor_distancia,
        "documento_envenenado": res_rag.documento_envenenado,
        "alerta_seguridad": res_rag.alerta_seguridad,
        "fragmentos": fragmentos_serializados,
    }
    ctx["rag"] = salida
    return salida


def _ejecutar_identificar_contravencion(args: ArgsIdentificarContravencion, ctx: dict[str, Any]) -> dict[str, Any]:
    contrav = buscar_contravencion_relacionada(args.consulta, args.articulo_recuperado)
    if contrav is None:
        ctx["contravencion"] = None
        return {"encontrada": False, "id_contravencion": None}
    ctx["contravencion"] = contrav
    return {
        "encontrada": True,
        "id_contravencion": contrav.id_contravencion,
        "codigo_csv": contrav.codigo_csv,
        "articulo": contrav.articulo,
        "clase": contrav.clase,
        "porcentaje_sbu": contrav.porcentaje_sbu,
        "descripcion": contrav.descripcion_infraccion,
    }


def _ejecutar_calcular_sancion(args: ArgsCalcularSancion, ctx: dict[str, Any]) -> dict[str, Any]:
    tabla = cargar_tabla()
    contrav = ctx.get("contravencion")
    if contrav is None or (
        contrav.id_contravencion != args.id_contravencion and contrav.codigo_csv != args.id_contravencion
    ):
        contrav = tabla.get(args.id_contravencion)
        if contrav is None:
            for item in tabla.values():
                if item.codigo_csv == args.id_contravencion:
                    contrav = item
                    break
    if contrav is None:
        raise ValueError(f"Contravención inexistente: {args.id_contravencion}")

    sancion_obj = calcular_sancion(contrav)
    pts_hoy = (
        sancion_obj.puntos_aplicables
        if sancion_obj.puntos_aplicables is not None
        else sancion_obj.puntos_reducidos
    )
    resultado = {
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
    ctx["sancion_calculada"] = resultado
    return resultado


def _ejecutar_verificar_cita_y_seguridad(args: ArgsVerificarCitaYSeguridad, ctx: dict[str, Any]) -> dict[str, Any]:
    _, envenenado_frag, motivo_frag = detectar_y_sanitizar_envenenamiento(args.texto_fragmento)
    rag_ctx = ctx.get("rag") or {}
    envenenado = bool(rag_ctx.get("documento_envenenado") or envenenado_frag)
    alerta = rag_ctx.get("alerta_seguridad") or motivo_frag
    cita_ok = args.articulo in set(args.articulos_recuperados) if args.articulos_recuperados else True
    resultado = {
        "cita_verificada": cita_ok,
        "documento_envenenado": envenenado,
        "alerta_seguridad": alerta,
    }
    ctx["verificacion"] = resultado
    return resultado


def _ejecutar_registrar_progreso(args: ArgsRegistrarProgreso, ctx: dict[str, Any]) -> dict[str, Any]:
    prog = registrar_progreso(
        args.usuario_id,
        es_correcta=args.es_correcta,
        multa_usd=args.multa_usd,
        puntos_reducidos=args.puntos_reducidos,
    )
    return {
        "usuario_id": prog.usuario_id,
        "total_evaluados": prog.total_evaluados,
        "aciertos": prog.aciertos,
        "fallos": prog.fallos,
        "multas_acumuladas_usd": prog.multas_acumuladas_usd,
        "puntos_perdidos": prog.puntos_perdidos,
        "nivel_sugerido": prog.nivel_sugerido,
    }


def _ejecutar_ajustar_dificultad(args: ArgsAjustarDificultad, ctx: dict[str, Any]) -> dict[str, Any]:
    return {"nivel_sugerido": ajustar_dificultad(args.ultimos_resultados)}


REGISTRO_HERRAMIENTAS: dict[str, tuple[type[BaseModel], Callable[[Any, dict[str, Any]], dict[str, Any]], str]] = {
    "buscar_normativa_rag": (
        ArgsBuscarNormativaRAG,
        _ejecutar_buscar_normativa_rag,
        "Recupera los artículos vigentes más cercanos desde ChromaDB usando embeddings E5 y filtro de vigencia.",
    ),
    "identificar_contravencion_coip": (
        ArgsIdentificarContravencion,
        _ejecutar_identificar_contravencion,
        "Identifica la contravención tipificada en el catálogo oficial del COIP relacionada con la consulta.",
    ),
    "calcular_sancion": (
        ArgsCalcularSancion,
        _ejecutar_calcular_sancion,
        "Calcula de forma determinista la multa en dólares según el porcentaje del SBU vigente y los puntos.",
    ),
    "verificar_cita_y_seguridad": (
        ArgsVerificarCitaYSeguridad,
        _ejecutar_verificar_cita_y_seguridad,
        "Verifica que la cita corresponda a un fragmento real y sanitiza instrucciones de inyección indirecta.",
    ),
    "registrar_progreso": (
        ArgsRegistrarProgreso,
        _ejecutar_registrar_progreso,
        "Registra el resultado de una práctica ciudadana acumulando multas y puntos simulados.",
    ),
    "ajustar_dificultad": (
        ArgsAjustarDificultad,
        _ejecutar_ajustar_dificultad,
        "Determina el nivel de dificultad adaptativa según la racha reciente del usuario.",
    ),
}

ESQUEMAS_HERRAMIENTAS_OPENAI: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": nombre,
            "description": descripcion,
            "parameters": esquema.model_json_schema(),
        },
    }
    for nombre, (esquema, _, descripcion) in REGISTRO_HERRAMIENTAS.items()
]


def despachar_herramienta(
    nombre: str,
    argumentos: str | dict[str, Any],
    contexto: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if nombre not in HERRAMIENTAS_PERMITIDAS or nombre not in REGISTRO_HERRAMIENTAS:
        raise HerramientaNoPermitidaError(nombre)
    esquema_cls, funcion, _ = REGISTRO_HERRAMIENTAS[nombre]
    datos_raw = json.loads(argumentos) if isinstance(argumentos, str) else argumentos
    args_validados = esquema_cls.model_validate(datos_raw)
    ctx = contexto if contexto is not None else {}
    return funcion(args_validados, ctx)


def _detectar_herramienta_prohibida(pregunta: str) -> str | None:
    q_norm = normalizar(pregunta)
    for nombre_tool, patrones in HERRAMIENTAS_FUERA_DE_ALCANCE.items():
        for pat in patrones:
            if re.search(pat, pregunta.lower()) or re.search(pat, q_norm):
                return nombre_tool
    return None


def _sintetizar_respuesta_final(pregunta: str, ctx: dict[str, Any]) -> str:
    rag_res = ctx.get("rag") or {}
    es_disputa = es_consulta_disputa(pregunta)
    if rag_res.get("abstencion") and not es_disputa:
        return rag_res.get("mensaje_abstencion") or MENSAJE_ABSTENCION_RAG

    fragmentos = rag_res.get("fragmentos") or []
    if es_disputa:
        art_ref = fragmentos[0].get("articulo", "389") if fragmentos else "389"
        return (
            f"Según el COIP (Art. {art_ref}), las contravenciones deben estar respaldadas en la boleta de citación. "
            f"{MENSAJE_DERIVACION_DISPUTA}"
        )

    top = fragmentos[0]
    cita_oficial = f"{top.get('documento', 'COIP')}, Art. {top.get('articulo', '')}"
    sancion = ctx.get("sancion_calculada")
    if sancion:
        texto = (
            f"Según el {cita_oficial} ({sancion['articulo']} · {sancion['clase']}), "
            f"la conducta «{sancion['descripcion']}» tiene una sanción del "
            f"{sancion['porcentaje_sbu']:g}% del SBU, calculada en código como "
            f"${sancion['multa_usd']:.2f} USD (SBU 2026: ${sancion['sbu_referencia_usd']:.2f} USD). "
            f"Puntos en el texto del artículo: {sancion['puntos_texto_coip']:g} pts "
            f"(puntos aplicables hoy tras reforma LOTTTSV 2021: {sancion['puntos_aplicables_hoy']:g} pts)."
        )
        if sancion.get("pena_adicional"):
            texto += f" Pena adicional prevista: {sancion['pena_adicional']}."
        return texto

    extracto = top["texto"][:340].rstrip() + ("..." if len(top["texto"]) > 340 else "")
    return f"Según el {cita_oficial}: «{extracto}»"


def _planificador_modelo_tool_calling(
    pregunta: str,
    mensajes: list[dict[str, Any]],
    ctx: dict[str, Any],
) -> MensajeModelo:
    tool_prohibida = _detectar_herramienta_prohibida(pregunta)
    if tool_prohibida:
        return MensajeModelo(
            role="assistant",
            content=None,
            tool_calls=[
                LlamadaHerramienta(
                    id="call_bloqueada_1",
                    function=FuncionToolCall(
                        name=tool_prohibida,
                        arguments=json.dumps({"motivo": pregunta}, ensure_ascii=False),
                    ),
                )
            ],
        )

    herramientas_ejecutadas = [m["name"] for m in mensajes if m.get("role") == "tool"]

    if "buscar_normativa_rag" not in herramientas_ejecutadas:
        return MensajeModelo(
            role="assistant",
            content=None,
            tool_calls=[
                LlamadaHerramienta(
                    id="call_rag_1",
                    function=FuncionToolCall(
                        name="buscar_normativa_rag",
                        arguments=json.dumps({"consulta": pregunta, "top_k": 5}, ensure_ascii=False),
                    ),
                )
            ],
        )

    rag_res = ctx.get("rag") or {}
    fragmentos = rag_res.get("fragmentos") or []
    mejor_art = fragmentos[0]["articulo"] if fragmentos else None

    if not rag_res.get("abstencion") and "identificar_contravencion_coip" not in herramientas_ejecutadas:
        return MensajeModelo(
            role="assistant",
            content=None,
            tool_calls=[
                LlamadaHerramienta(
                    id="call_id_contrav_2",
                    function=FuncionToolCall(
                        name="identificar_contravencion_coip",
                        arguments=json.dumps(
                            {"consulta": pregunta, "articulo_recuperado": mejor_art},
                            ensure_ascii=False,
                        ),
                    ),
                )
            ],
        )

    contrav = ctx.get("contravencion")
    if (
        not rag_res.get("abstencion")
        and contrav is not None
        and "calcular_sancion" not in herramientas_ejecutadas
    ):
        return MensajeModelo(
            role="assistant",
            content=None,
            tool_calls=[
                LlamadaHerramienta(
                    id="call_calc_3",
                    function=FuncionToolCall(
                        name="calcular_sancion",
                        arguments=json.dumps(
                            {"id_contravencion": contrav.id_contravencion},
                            ensure_ascii=False,
                        ),
                    ),
                )
            ],
        )

    if "verificar_cita_y_seguridad" not in herramientas_ejecutadas:
        arts_disp = [f["articulo"] for f in fragmentos]
        texto_top = fragmentos[0]["texto"] if fragmentos else ""
        return MensajeModelo(
            role="assistant",
            content=None,
            tool_calls=[
                LlamadaHerramienta(
                    id="call_verif_4",
                    function=FuncionToolCall(
                        name="verificar_cita_y_seguridad",
                        arguments=json.dumps(
                            {
                                "articulo": mejor_art or "ninguno",
                                "articulos_recuperados": arts_disp,
                                "texto_fragmento": texto_top,
                            },
                            ensure_ascii=False,
                        ),
                    ),
                )
            ],
        )

    return MensajeModelo(
        role="assistant",
        content=_sintetizar_respuesta_final(pregunta, ctx),
        tool_calls=None,
    )


def _solicitar_paso_modelo(
    pregunta: str,
    mensajes: list[dict[str, Any]],
    ctx: dict[str, Any],
    cliente_llm: Any | None = None,
) -> MensajeModelo:
    if cliente_llm is not None:
        msg, _, _, _, _ = cliente_llm.llamar_con_herramientas(mensajes, ESQUEMAS_HERRAMIENTAS_OPENAI)
        tcs = getattr(msg, "tool_calls", None)
        if tcs:
            llamadas = [
                LlamadaHerramienta(
                    id=getattr(tc, "id", f"call_{i+1}"),
                    function=FuncionToolCall(
                        name=tc.function.name,
                        arguments=tc.function.arguments,
                    ),
                )
                for i, tc in enumerate(tcs)
            ]
            return MensajeModelo(role="assistant", content=getattr(msg, "content", None), tool_calls=llamadas)
        return MensajeModelo(role="assistant", content=getattr(msg, "content", ""), tool_calls=None)
    return _planificador_modelo_tool_calling(pregunta, mensajes, ctx)


def ejecutar_agente_consulta(
    pregunta: str,
    fragmentos_extra: list[dict] | None = None,
    simular_fallo_herramienta: bool = False,
    cliente_llm: Any | None = None,
) -> dict[str, Any]:
    bitacora: list[dict[str, str]] = []
    estaciones: list[dict[str, Any]] = []
    vueltas = 0
    parametros = cargar_parametros()
    ctx: dict[str, Any] = {"fragmentos_extra": fragmentos_extra}

    mensajes: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT_AGENTE},
        {"role": "user", "content": pregunta},
    ]

    if simular_fallo_herramienta:
        while vueltas < TOPE_VUELTAS:
            vueltas += 1
            call_id = f"call_retry_{vueltas}"
            mensajes.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": call_id,
                        "type": "function",
                        "function": {
                            "name": "buscar_normativa_rag",
                            "arguments": json.dumps({"consulta": pregunta, "top_k": 5}, ensure_ascii=False),
                        },
                    }
                ],
            })
            mensajes.append({
                "role": "tool",
                "tool_call_id": call_id,
                "name": "buscar_normativa_rag",
                "content": json.dumps({"ok": False, "error": "Timeout transitorio en herramienta"}, ensure_ascii=False),
            })
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
                "mensajes": mensajes,
                "esquemas_herramientas": ESQUEMAS_HERRAMIENTAS_OPENAI,
            },
            "automatizacion": {
                "modo": "revision_humana",
                "confianza": 0.0,
                "estaciones": estaciones,
            },
            "aviso": parametros["aviso_educativo"],
        }

    respuesta_final_modelo: str | None = None

    while vueltas < TOPE_VUELTAS:
        msg_modelo = _solicitar_paso_modelo(pregunta, mensajes, ctx, cliente_llm=cliente_llm)

        if not msg_modelo.tool_calls:
            respuesta_final_modelo = msg_modelo.content or _sintetizar_respuesta_final(pregunta, ctx)
            mensajes.append({"role": "assistant", "content": respuesta_final_modelo})
            break

        mensajes.append({
            "role": "assistant",
            "content": msg_modelo.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg_modelo.tool_calls
            ],
        })

        for tc in msg_modelo.tool_calls:
            vueltas += 1
            nombre_fn = tc.function.name
            args_str = tc.function.arguments

            try:
                resultado_tool = despachar_herramienta(nombre_fn, args_str, contexto=ctx)
            except HerramientaNoPermitidaError:
                mensajes.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": nombre_fn,
                    "content": json.dumps(
                        {"ok": False, "error": f"Herramienta '{nombre_fn}' bloqueada por fuera de alcance"},
                        ensure_ascii=False,
                    ),
                })
                bitacora.append({
                    "vuelta": str(vueltas),
                    "fase": "Observar -> Pensar",
                    "herramienta": nombre_fn,
                    "detalle": (
                        f"El modelo solicitó `{nombre_fn}`, la cual NO está en la lista cerrada "
                        "HERRAMIENTAS_PERMITIDAS. Se rechaza en código."
                    ),
                })
                estaciones = [
                    {"estacion": "1 · Clasificar", "actor": "IA", "resultado": "accion_fuera_de_alcance", "confianza": 0.98},
                    {"estacion": "2 · Extraer datos", "actor": "IA", "resultado": f'{{"herramienta_solicitada": "{nombre_fn}"}}'},
                    {"estacion": "3 · Reglas (código)", "actor": "código", "resultado": f"{nombre_fn} not in HERRAMIENTAS_PERMITIDAS -> BLOQUEAR"},
                    {"estacion": "4 · Actuar", "actor": "sistema", "resultado": "Rechazo seguro y oferta de orientación normativa legal"},
                ]
                return {
                    "pregunta": pregunta,
                    "respuesta": (
                        f"No tengo permiso ni herramienta para ejecutar `{nombre_fn}`. "
                        "Vía Segura es un simulador educativo de alcance controlado: puedo buscar el artículo del COIP "
                        "y calcular de forma referencial la multa legal, pero nunca anular boletas ni sugerir cómo evadir controles."
                    ),
                    "tipo": "fuera_de_alcance_herramienta",
                    "abstencion": True,
                    "citas": [],
                    "cita_verificada": True,
                    "mejor_distancia": 1.0,
                    "resumen_clase": f"Grupo 8: herramienta `{nombre_fn}` fuera de alcance -> RECHAZADA en código",
                    "sancion_calculada": None,
                    "documento_envenenado": False,
                    "alerta_seguridad": f"Alcance controlado: `{nombre_fn}` no pertenece a HERRAMIENTAS_PERMITIDAS.",
                    "fragmentos": [],
                    "agente": {
                        "vueltas_usadas": vueltas,
                        "tope_vueltas": TOPE_VUELTAS,
                        "herramientas_permitidas": HERRAMIENTAS_PERMITIDAS,
                        "herramientas_fuera_de_alcance": list(HERRAMIENTAS_FUERA_DE_ALCANCE.keys()),
                        "herramienta_bloqueada": nombre_fn,
                        "bitacora": bitacora,
                        "mensajes": mensajes,
                        "esquemas_herramientas": ESQUEMAS_HERRAMIENTAS_OPENAI,
                    },
                    "automatizacion": {
                        "modo": "rechazo_alcance_controlado",
                        "confianza": 0.98,
                        "estaciones": estaciones,
                    },
                    "aviso": parametros["aviso_educativo"],
                }

            mensajes.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "name": nombre_fn,
                "content": json.dumps(resultado_tool, ensure_ascii=False),
            })

            detalle_paso = _formatear_detalle_bitacora(nombre_fn, resultado_tool)
            fase_paso = (
                "Verificar (Cierre del bucle)"
                if nombre_fn == "verificar_cita_y_seguridad"
                else "Observar -> Pensar -> Actuar -> Verificar"
            )
            bitacora.append({
                "vuelta": str(vueltas),
                "fase": fase_paso,
                "herramienta": nombre_fn,
                "detalle": detalle_paso,
            })

            if vueltas >= TOPE_VUELTAS:
                break

    if respuesta_final_modelo is None:
        respuesta_final_modelo = _sintetizar_respuesta_final(pregunta, ctx)
        mensajes.append({"role": "assistant", "content": respuesta_final_modelo})

    rag_res = ctx.get("rag") or {
        "abstencion": True,
        "mensaje_abstencion": MENSAJE_ABSTENCION_RAG,
        "cita_principal": None,
        "mejor_distancia": 0.85,
        "documento_envenenado": False,
        "alerta_seguridad": None,
        "fragmentos": [],
    }
    fragmentos = rag_res.get("fragmentos") or []
    mejor_art = fragmentos[0]["articulo"] if fragmentos else "ninguno"
    mejor_dist = float(rag_res.get("mejor_distancia", 0.85))
    sancion_dict = ctx.get("sancion_calculada")
    verif = ctx.get("verificacion") or {}

    es_disputa = es_consulta_disputa(pregunta)
    abstencion_final = bool(rag_res.get("abstencion") or es_disputa)

    if rag_res.get("abstencion") and not es_disputa:
        tipo_resp = "silencio"
        citas_lista: list[str] = []
        resumen_cls = (
            f"Grupo 8: nuestra pregunta «{pregunta}» no encontró artículo cercano "
            f"(mejor distancia {mejor_dist:.2f} > umbral {UMBRAL_DISTANCIA_COSENO}) -> SILENCIO"
        )
    elif es_disputa:
        tipo_resp = "derivacion_disputa"
        citas_lista = [rag_res["cita_principal"]] if rag_res.get("cita_principal") else ["COIP, Art. 389"]
        art_ref = mejor_art if mejor_art != "ninguno" else "389"
        resumen_cls = (
            f"Grupo 8: nuestra pregunta «{pregunta}» encontró el Art. {art_ref} en el puesto 1, "
            "pero al ser un caso en disputa cita la norma y deriva sin dictaminar."
        )
    else:
        tipo_resp = "con_fuente"
        top_f = fragmentos[0]
        cita_oficial = f"{top_f.get('documento', 'COIP')}, Art. {top_f.get('articulo', '')}"
        citas_lista = [cita_oficial]
        resumen_cls = (
            f"Grupo 8: nuestra pregunta «{pregunta}» encontró el Art. {mejor_art} en el puesto {top_f.get('puesto', 1)}"
        )

    confianza = round(max(0.35, min(0.98, 1.0 - mejor_dist)), 2)
    modo_auto = (
        "automatico"
        if (not abstencion_final and confianza >= UMBRAL_CONFIANZA_AUTOMATICA and not es_disputa)
        else "revision_humana_o_derivacion"
    )

    estaciones = [
        {
            "estacion": "1 · Clasificar",
            "actor": "IA",
            "resultado": tipo_resp,
            "confianza": confianza,
        },
        {
            "estacion": "2 · Extraer datos",
            "actor": "IA",
            "resultado": json_resumen_extraccion(mejor_art, sancion_dict),
        },
        {
            "estacion": "3 · Reglas (código)",
            "actor": "código",
            "resultado": (
                f"distancia {mejor_dist:.2f} <= {UMBRAL_DISTANCIA_COSENO} y SBU=${parametros['sbu_usd']:.2f} -> responder con cita"
                if not abstencion_final
                else "baja similitud o caso en disputa -> desviar a orientación humana / ANT"
            ),
        },
        {
            "estacion": "4 · Actuar",
            "actor": "sistema",
            "resultado": (
                f"Respuesta fundamentada con cita {citas_lista}"
                if not abstencion_final
                else "Silencio / derivación a autoridad competente (ANT / consultorio jurídico)"
            ),
        },
    ]

    return {
        "pregunta": pregunta,
        "abstencion": abstencion_final,
        "tipo": tipo_resp,
        "respuesta": respuesta_final_modelo,
        "citas": citas_lista,
        "cita_verificada": bool(verif.get("cita_verificada", True)),
        "mejor_distancia": mejor_dist,
        "umbral_distancia": UMBRAL_DISTANCIA_COSENO,
        "modelo_embeddings": MODELO_EMBEDDINGS,
        "resumen_clase": resumen_cls,
        "sancion_calculada": sancion_dict,
        "documento_envenenado": bool(verif.get("documento_envenenado", rag_res.get("documento_envenenado", False))),
        "alerta_seguridad": verif.get("alerta_seguridad") or rag_res.get("alerta_seguridad"),
        "fragmentos": [] if (rag_res.get("abstencion") and not es_disputa) else fragmentos,
        "agente": {
            "vueltas_usadas": vueltas,
            "tope_vueltas": TOPE_VUELTAS,
            "herramientas_permitidas": HERRAMIENTAS_PERMITIDAS,
            "herramientas_fuera_de_alcance": list(HERRAMIENTAS_FUERA_DE_ALCANCE.keys()),
            "herramienta_bloqueada": None,
            "bitacora": bitacora,
            "mensajes": mensajes,
            "esquemas_herramientas": ESQUEMAS_HERRAMIENTAS_OPENAI,
        },
        "automatizacion": {
            "modo": modo_auto,
            "confianza": confianza,
            "estaciones": estaciones,
        },
        "aviso": parametros["aviso_educativo"],
    }


def _formatear_detalle_bitacora(nombre_fn: str, resultado: dict[str, Any]) -> str:
    if nombre_fn == "buscar_normativa_rag":
        frags = resultado.get("fragmentos") or []
        mejor = frags[0]["articulo"] if frags else "ninguno"
        dist = float(resultado.get("mejor_distancia", 1.0))
        return (
            f"Consulta en ChromaDB (`where={{'vigente': True}}`, top_k=5): "
            f"{len(frags)} fragmentos recuperados; mejor artículo={mejor} (distancia coseno={dist:.2f})."
        )
    if nombre_fn == "identificar_contravencion_coip":
        if resultado.get("encontrada"):
            return f"Contravención identificada: `{resultado['id_contravencion']}` ({resultado['articulo']})."
        return "Consulta normativa general o reglamentaria sin multa pecuniaria directa."
    if nombre_fn == "calcular_sancion":
        return (
            f"Contravención `{resultado['id_contravencion']}` ({resultado['porcentaje_sbu']:g}% SBU): "
            f"multa=${resultado['multa_usd']:.2f} USD (SBU=${resultado['sbu_referencia_usd']:.2f}), "
            f"puntos COIP={resultado['puntos_texto_coip']:g}."
        )
    if nombre_fn == "verificar_cita_y_seguridad":
        return (
            f"Cita verificada={resultado.get('cita_verificada')}; "
            f"documento_envenenado={resultado.get('documento_envenenado')}."
        )
    return json.dumps(resultado, ensure_ascii=False)


def json_resumen_extraccion(articulo: str, sancion: dict[str, Any] | None) -> str:
    if sancion:
        return (
            f'{{"articulo": "Art. {articulo}", "codigo": "{sancion["codigo_csv"]}", '
            f'"porcentaje_sbu": {sancion["porcentaje_sbu"]}, "multa_usd": {sancion["multa_usd"]}}}'
        )
    return f'{{"articulo_detectado": "{articulo}"}}'
