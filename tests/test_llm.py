"""Pruebas del servicio de IA con un DOBLE del modelo: no gastan API y corren en un segundo.

    pytest -q
"""
import json
from types import SimpleNamespace as NS

import httpx
import openai
import pytest

from typing import Literal

from app.config import Config, Proveedor
from app.schemas import Estricto
from app.services.llm import ClienteLLM, ProveedorNoDisponible, SalidaInvalida


class Clasificacion(Estricto):
    """Esquema genérico del kit, solo para probar el servicio de IA (reintentos, respaldo, JSON)."""
    es_soporte_tecnologico: bool
    categoria: Literal["hardware", "software", "red", "accesos", "otro"]
    impacto: Literal["bajo", "medio", "alto"]
    urgencia: Literal["baja", "media", "alta"]
    resumen: str
    datos_faltantes: list[str]

BUENA = json.dumps({"es_soporte_tecnologico": True, "categoria": "accesos", "impacto": "alto", "urgencia": "alta",
                    "resumen": "Ventas no puede entrar a facturación.", "datos_faltantes": []})


def respuesta(texto):
    return NS(choices=[NS(message=NS(content=texto), finish_reason="stop")], usage=NS(prompt_tokens=10, completion_tokens=5))


def error_http(clase, codigo, cabeceras=None):
    req = httpx.Request("POST", "https://proveedor.test/v1/chat/completions")
    return clase("simulado", response=httpx.Response(codigo, headers=cabeceras or {}, request=req), body=None)


class Doble:
    """Imita a client.chat.completions.create: devuelve (o lanza) lo que le digamos, en orden."""

    def __init__(self, guion):
        self.guion, self.llamadas = list(guion), []
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, **kw):
        self.llamadas.append(kw)
        paso = self.guion.pop(0)
        if isinstance(paso, Exception):
            raise paso
        return respuesta(paso)


def cliente(principal, respaldo=None, reintentos=3):
    cfg = Config(principal=Proveedor("a", "u", "k", "modelo-a"),
                 respaldo=Proveedor("b", "u", "k", "modelo-b") if respaldo is not None else None,
                 timeout_s=5, max_tokens=100, reintentos=reintentos, razonamiento=None)
    esperas = []
    c = ClienteLLM(cfg, clientes={"a": principal, **({"b": respaldo} if respaldo else {})}, dormir=esperas.append)
    return c, esperas


def test_json_valido():
    c, _ = cliente(Doble([BUENA]))
    r = c.generar_json("sys", "texto", Clasificacion)
    assert r.datos.categoria == "accesos" and r.proveedor == "a" and r.intentos == 1


def test_pide_el_esquema_al_proveedor():
    d = Doble([BUENA])
    cliente(d)[0].generar_json("sys", "texto", Clasificacion)
    rf = d.llamadas[0]["response_format"]
    assert rf["type"] == "json_schema" and rf["json_schema"]["strict"] is True


def test_json_invalido_se_corrige_una_vez():
    d = Doble(['{"categoria": "teclado"}', BUENA])
    r = cliente(d)[0].generar_json("sys", "texto", Clasificacion)
    assert r.datos.impacto == "alto"
    assert "no cumple el esquema" in d.llamadas[1]["messages"][-1]["content"]


def test_json_invalido_dos_veces_va_a_revision_humana():
    c, _ = cliente(Doble(["no es json", "tampoco"]))
    with pytest.raises(SalidaInvalida):
        c.generar_json("sys", "texto", Clasificacion)


def test_429_respeta_retry_after_y_reintenta():
    c, esperas = cliente(Doble([error_http(openai.RateLimitError, 429, {"retry-after": "2"}), BUENA]))
    r = c.generar_json("sys", "texto", Clasificacion)
    assert 2.0 <= esperas[0] <= 2.5 and r.intentos == 2  # lo pedido + un poco de azar


def test_espera_exponencial_sin_retry_after():
    c, esperas = cliente(Doble([error_http(openai.InternalServerError, 503), error_http(openai.InternalServerError, 503), BUENA]))
    c.generar_json("sys", "texto", Clasificacion)
    assert 0.5 <= esperas[0] <= 1 and 1 <= esperas[1] <= 2  # 1 s y 2 s, con azar


def test_respuesta_vacia_se_reintenta():
    c, _ = cliente(Doble(["", BUENA]))
    assert c.generar_json("sys", "texto", Clasificacion).intentos == 2


def test_principal_caido_pasa_al_respaldo():
    tiempo = openai.APITimeoutError(request=httpx.Request("POST", "https://x"))
    c, _ = cliente(Doble([tiempo, tiempo, tiempo]), Doble([BUENA]))
    assert c.generar_json("sys", "texto", Clasificacion).proveedor == "b"


def test_clave_invalida_no_se_reintenta():
    principal = Doble([error_http(openai.AuthenticationError, 401)])
    c, esperas = cliente(principal, Doble([BUENA]))
    assert c.generar_json("sys", "texto", Clasificacion).proveedor == "b"
    assert len(principal.llamadas) == 1 and esperas == []


def test_todos_caidos_da_error_claro():
    caida = lambda: error_http(openai.RateLimitError, 429, {"retry-after": "1"})  # noqa: E731
    c, _ = cliente(Doble([caida() for _ in range(3)]), Doble([caida() for _ in range(3)]))
    with pytest.raises(ProveedorNoDisponible) as e:
        c.generar_json("sys", "texto", Clasificacion)
    assert "no está disponible" in e.value.mensaje_usuario


def test_retry_after_muy_largo_va_directo_al_respaldo():
    c, esperas = cliente(Doble([error_http(openai.RateLimitError, 429, {"retry-after": "3600"})]), Doble([BUENA]))
    assert c.generar_json("sys", "texto", Clasificacion).proveedor == "b" and esperas == []
