from __future__ import annotations

import json
import logging
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Generic, Iterator, TypeVar

import openai
from openai import OpenAI
from pydantic import BaseModel, ValidationError

from app.config import Config, Proveedor, cargar_config

T = TypeVar("T", bound=BaseModel)

Path("logs").mkdir(exist_ok=True)
log = logging.getLogger("llm")
if not log.handlers:
    log.setLevel(logging.INFO)
    _f = logging.FileHandler("logs/llm.jsonl", encoding="utf-8")
    _f.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(_f)
    _c = logging.StreamHandler()
    _c.setFormatter(logging.Formatter("  [llm] %(message)s"))
    log.addHandler(_c)


def _registrar(**datos) -> None:
    log.info(json.dumps(datos, ensure_ascii=False))


class ErrorLLM(Exception):
    mensaje_usuario = "El asistente no pudo responder. Inténtalo de nuevo."


class ProveedorNoDisponible(ErrorLLM):
    mensaje_usuario = "El asistente no está disponible en este momento. Intenta de nuevo en unos minutos."


class SalidaInvalida(ErrorLLM):
    mensaje_usuario = "No pudimos procesar la respuesta automáticamente. Tu solicitud quedó para revisión humana."


class _FalloProveedor(Exception):
    pass


class _RespuestaVacia(Exception):
    pass


REINTENTABLES = (openai.RateLimitError, openai.APITimeoutError, openai.APIConnectionError, openai.InternalServerError)
DEFINITIVOS = (openai.AuthenticationError, openai.PermissionDeniedError, openai.NotFoundError, openai.BadRequestError)
ESPERA_MAXIMA_S = 20


@dataclass
class Resultado(Generic[T]):
    datos: T | str
    proveedor: str
    modelo: str
    tokens_entrada: int | None
    tokens_salida: int | None
    latencia_ms: int
    intentos: int


def espera_exponencial(intento: int, base: float = 1.0) -> float:
    tope = base * 2 ** (intento - 1)
    return tope / 2 + random.uniform(0, tope / 2)


def _retry_after(error: Exception) -> float | None:
    respuesta = getattr(error, "response", None)
    valor = respuesta.headers.get("retry-after") if respuesta is not None else None
    try:
        return float(valor) if valor is not None else None
    except ValueError:
        return None


def _limpiar_json(texto: str) -> str:
    texto = texto.strip()
    m = re.match(r"^```(?:json)?\s*(.*?)\s*```$", texto, re.S)
    return m.group(1) if m else texto


class ClienteLLM:
    def __init__(self, config: Config | None = None, clientes: dict | None = None,
                 dormir: Callable[[float], None] = time.sleep):
        self.config = config or cargar_config()
        self.proveedores: list[Proveedor] = [p for p in (self.config.principal, self.config.respaldo) if p]
        self.dormir = dormir
        self._clientes = clientes or {
            p.nombre: OpenAI(
                api_key=p.api_key,
                base_url=p.base_url,
                timeout=self.config.timeout_s,
                max_retries=0,
            )
            for p in self.proveedores
        }

    def _llamar(self, p: Proveedor, mensajes: list[dict], extra: dict) -> tuple[object, int, int]:
        cliente = self._clientes[p.nombre]
        opciones = {"max_tokens": self.config.max_tokens, **extra}
        if self.config.razonamiento and p.nombre != "simulado":
            opciones["reasoning_effort"] = self.config.razonamiento
        for intento in range(1, self.config.reintentos + 1):
            t0 = time.monotonic()
            try:
                r = cliente.chat.completions.create(model=p.modelo, messages=mensajes, **opciones)
                ms = int((time.monotonic() - t0) * 1000)
                contenido = (r.choices[0].message.content or "") if r.choices else ""
                if not contenido.strip():
                    raise _RespuestaVacia()
                uso = getattr(r, "usage", None)
                _registrar(
                    evento="ok",
                    proveedor=p.nombre,
                    modelo=p.modelo,
                    intento=intento,
                    latencia_ms=ms,
                    tokens_entrada=getattr(uso, "prompt_tokens", None),
                    tokens_salida=getattr(uso, "completion_tokens", None),
                    fin=r.choices[0].finish_reason,
                )
                return r, ms, intento
            except DEFINITIVOS as e:
                _registrar(
                    evento="error_definitivo",
                    proveedor=p.nombre,
                    intento=intento,
                    tipo=type(e).__name__,
                    estado_http=getattr(e, "status_code", None),
                )
                raise _FalloProveedor() from e
            except (*REINTENTABLES, _RespuestaVacia) as e:
                pedida = _retry_after(e)
                espera = pedida + random.uniform(0, 0.5) if pedida is not None else espera_exponencial(intento)
                _registrar(
                    evento="reintento" if intento < self.config.reintentos else "agotado",
                    proveedor=p.nombre,
                    intento=intento,
                    tipo=type(e).__name__,
                    estado_http=getattr(e, "status_code", None),
                    espera_s=round(espera, 2),
                )
                if intento == self.config.reintentos or espera > ESPERA_MAXIMA_S:
                    raise _FalloProveedor() from e
                self.dormir(espera)
        raise _FalloProveedor()

    def _con_respaldo(self, mensajes: list[dict], extra: dict):
        for p in self.proveedores:
            try:
                r, ms, intentos = self._llamar(p, mensajes, extra)
                return p, r, ms, intentos
            except _FalloProveedor:
                continue
        _registrar(evento="sin_proveedor")
        raise ProveedorNoDisponible()

    def generar_texto(self, system: str, mensajes: list[dict]) -> Resultado[str]:
        p, r, ms, intentos = self._con_respaldo([{"role": "system", "content": system}, *mensajes], {})
        uso = getattr(r, "usage", None)
        return Resultado(
            r.choices[0].message.content,
            p.nombre,
            p.modelo,
            getattr(uso, "prompt_tokens", None),
            getattr(uso, "completion_tokens", None),
            ms,
            intentos,
        )

    def generar_json(self, system: str, usuario: str, esquema: type[T]) -> Resultado[T]:
        formato = {
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": esquema.__name__, "strict": True, "schema": esquema.model_json_schema()},
            }
        }
        mensajes = [{"role": "system", "content": system}, {"role": "user", "content": usuario}]
        p, r, ms, intentos = self._con_respaldo(mensajes, formato)
        texto = r.choices[0].message.content
        try:
            datos = esquema.model_validate_json(_limpiar_json(texto))
        except ValidationError as e:
            _registrar(evento="salida_invalida", proveedor=p.nombre, errores=e.error_count())
            correccion = mensajes + [
                {"role": "assistant", "content": texto},
                {
                    "role": "user",
                    "content": "Tu respuesta no cumple el esquema. Errores:\n"
                    + "\n".join(f"- {'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors())
                    + "\nDevuelve SOLO el JSON corregido.",
                },
            ]
            p, r, ms2, _ = self._con_respaldo(correccion, formato)
            ms += ms2
            try:
                datos = esquema.model_validate_json(_limpiar_json(r.choices[0].message.content))
            except ValidationError as e2:
                _registrar(evento="salida_invalida_final", proveedor=p.nombre, errores=e2.error_count())
                raise SalidaInvalida() from e2
        uso = getattr(r, "usage", None)
        return Resultado(
            datos,
            p.nombre,
            p.modelo,
            getattr(uso, "prompt_tokens", None),
            getattr(uso, "completion_tokens", None),
            ms,
            intentos,
        )

    def generar_stream(self, system: str, mensajes: list[dict]) -> Iterator[str]:
        completos = [{"role": "system", "content": system}, *mensajes]
        for p in self.proveedores:
            try:
                flujo = self._clientes[p.nombre].chat.completions.create(
                    model=p.modelo,
                    messages=completos,
                    stream=True,
                    max_tokens=self.config.max_tokens,
                )
                for trozo in flujo:
                    if trozo.choices and trozo.choices[0].delta.content:
                        yield trozo.choices[0].delta.content
                return
            except (*REINTENTABLES, *DEFINITIVOS) as e:
                _registrar(evento="stream_fallo", proveedor=p.nombre, tipo=type(e).__name__)
                continue
        raise ProveedorNoDisponible()


def cargar_prompt(nombre: str) -> str:
    return (Path(__file__).resolve().parent.parent / "prompts" / f"{nombre}.md").read_text(encoding="utf-8")
