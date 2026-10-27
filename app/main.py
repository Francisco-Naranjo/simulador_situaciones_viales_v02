"""API del Simulador Educativo de Situaciones Viales «Vía Segura» (caso 08).

    uvicorn app.main:app --reload        →  http://127.0.0.1:8000/docs

Endpoints:
    GET  /health        estado del servicio
    POST /escenarios    genera un escenario validado contra la tabla (usa el modelo)
    POST /evaluaciones  evalúa la respuesta y calcula la sanción (100 % código, sin modelo)

Los errores se devuelven como RFC 9457 (application/problem+json) y nunca exponen el
error crudo del proveedor.
"""
from __future__ import annotations

import os
import re
import threading
from collections import OrderedDict
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import cargar_config
from app.parametros import cargar_parametros
from app.schemas import (Contravencion, EscenarioPublico, EscenarioVialSchema, OpcionPublica,
                         ResultadoEvaluacion, SolicitudEscenario, SolicitudEvaluacion)
from app.services.generador import generar_escenario
from app.services.limite_tasa import LimitadorTasa
from app.services.llm import ClienteLLM, ErrorLLM
from app.tools.contravenciones import EscenarioInvalido, FueraDeDominio, cargar_tabla
from app.tools.evaluar_respuesta import evaluar_respuesta

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
MAX_ESCENARIOS = 1000


@asynccontextmanager
async def ciclo_de_vida(_: FastAPI):
    # Falla al ARRANCAR con un mensaje claro si falta la clave o la tabla está mal,
    # en lugar de fallar a mitad de una demo.
    cfg = cargar_config()
    cargar_tabla()
    cargar_parametros()
    srv = None
    if cfg.principal.nombre == "simulado":
        import sys
        from app.config import CATALOGO
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        import servidor_simulado
        srv = servidor_simulado.iniciar(puerto=0, limite=100, ventana=10)
        CATALOGO["simulado"]["base_url"] = f"http://127.0.0.1:{srv.server_port}/v1"
        obtener_llm.cache_clear()
    try:
        yield
    finally:
        if srv is not None:
            srv.shutdown()
            srv.server_close()
            CATALOGO["simulado"]["base_url"] = "http://127.0.0.1:8099/v1"
            obtener_llm.cache_clear()


app = FastAPI(title="Vía Segura · Simulador educativo de situaciones viales", version="0.2.0",
              lifespan=ciclo_de_vida)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",") if o.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Session-ID"],
    expose_headers=["Retry-After"],  # sin esto el navegador no deja leer Retry-After
)

_lim = cargar_parametros()["limite_tasa"]
limitador = LimitadorTasa(_lim["capacidad"], _lim["recarga_por_segundo"])

# Escenarios emitidos y aún no evaluados: la respuesta correcta NUNCA viaja al navegador.
_escenarios: OrderedDict[str, tuple[str, EscenarioVialSchema, Contravencion]] = OrderedDict()
_candado = threading.Lock()


@lru_cache
def obtener_llm() -> ClienteLLM:
    return ClienteLLM()


# ---------------------------------------------------------------- errores RFC 9457
class Problema(Exception):
    def __init__(self, estado: int, titulo: str, detalle: str, tipo: str = "about:blank",
                 cabeceras: dict | None = None):
        self.estado, self.titulo, self.detalle, self.tipo, self.cabeceras = estado, titulo, detalle, tipo, cabeceras


def _problema(estado: int, titulo: str, detalle: str, tipo: str = "about:blank", cabeceras=None, **extra):
    return JSONResponse({"type": tipo, "title": titulo, "status": estado, "detail": detalle, **extra},
                        status_code=estado, headers=cabeceras, media_type="application/problem+json")


@app.exception_handler(Problema)
async def _manejar_problema(_: Request, p: Problema):
    return _problema(p.estado, p.titulo, p.detalle, p.tipo, p.cabeceras)


@app.exception_handler(RequestValidationError)
async def _manejar_validacion(_: Request, e: RequestValidationError):
    errores = [{"campo": ".".join(str(x) for x in err["loc"][1:]), "mensaje": err["msg"]} for err in e.errors()]
    return _problema(422, "Datos de entrada inválidos", "Revisa los campos indicados.", errores=errores)


# ---------------------------------------------------------------- sesión anónima (LOPDP)
def clave_sesion(request: Request) -> str:
    """Identificador ANÓNIMO generado por el navegador (crypto.randomUUID). No se piden datos
    personales. Si no llega o no es un UUID, se usa la IP solo para el límite de tasa."""
    sid = request.headers.get("X-Session-ID", "")
    return sid.lower() if UUID_RE.match(sid) else f"ip:{request.client.host if request.client else 'desconocida'}"


# ---------------------------------------------------------------- endpoints
@app.get("/health")
def health():
    return {"estado": "ok"}


@app.get("/rag/buscar")
def buscar_rag(q: str, top_k: int = 5, documento: str | None = None, clase: str | None = None):
    """Recupera artículos vigentes del índice RAG aplicando filtros de metadatos antes de top_k."""
    from dataclasses import asdict
    from app.services.rag import recuperar
    filtro = {"vigente": "true"}
    if documento:
        filtro["documento"] = documento
    if clase:
        filtro["clase"] = clase
    return asdict(recuperar(q, top_k=min(max(1, top_k), 10), where=filtro))


@app.post("/escenarios", response_model=EscenarioPublico)
def crear_escenario(solicitud: SolicitudEscenario, sesion: str = Depends(clave_sesion),
                    llm: ClienteLLM = Depends(obtener_llm)):
    espera = limitador.consumir(sesion)
    if espera:
        raise Problema(429, "Demasiadas solicitudes",
                       f"Has generado muchos escenarios seguidos. Intenta de nuevo en {int(espera)} s.",
                       cabeceras={"Retry-After": str(int(espera))})
    try:
        esc, contravencion = generar_escenario(llm, solicitud)
    except FueraDeDominio:
        raise Problema(422, "Fuera del dominio vial",
                       "FALTA: Información fuera del dominio normativo vial de Ecuador. "
                       "Prueba con un tema de tránsito (velocidad, señales, peatones, documentos…).",
                       tipo="/problemas/fuera-de-dominio")
    except EscenarioInvalido:
        raise Problema(502, "Escenario descartado",
                       "El modelo propuso un escenario que no corresponde a la tabla oficial y se descartó. "
                       "Intenta generar otro.", tipo="/problemas/escenario-invalido")
    except ErrorLLM as e:
        raise Problema(503, "Servicio no disponible", e.mensaje_usuario, cabeceras={"Retry-After": "30"})

    with _candado:
        _escenarios[esc.id_escenario] = (sesion, esc, contravencion)
        while len(_escenarios) > MAX_ESCENARIOS:
            _escenarios.popitem(last=False)
    return EscenarioPublico(
        id_escenario=esc.id_escenario, perfil=esc.perfil, nivel_dificultad=esc.nivel_dificultad,
        situacion=esc.situacion,
        opciones=[OpcionPublica(id_opcion=o.id_opcion, texto=o.texto)
                  for o in sorted(esc.opciones, key=lambda o: o.id_opcion)],
        aviso=cargar_parametros()["aviso_educativo"],
    )


@app.post("/evaluaciones", response_model=ResultadoEvaluacion)
def evaluar(solicitud: SolicitudEvaluacion, sesion: str = Depends(clave_sesion)):
    with _candado:
        registro = _escenarios.get(solicitud.id_escenario)
        if registro is None or registro[0] != sesion:
            raise Problema(404, "Escenario no encontrado",
                           "El escenario no existe, ya fue respondido o expiró. Genera uno nuevo.")
        del _escenarios[solicitud.id_escenario]  # una sola respuesta por escenario
    _, esc, contravencion = registro
    return evaluar_respuesta(esc, contravencion, solicitud.respuesta)


# Servir la interfaz compilada de frontend/dist si existe
from pathlib import Path
from fastapi.staticfiles import StaticFiles

_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="frontend")
