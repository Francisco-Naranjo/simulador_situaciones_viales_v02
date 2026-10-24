"""Configuración leída del archivo .env.

Regla del seminario: lo que es secreto vive en variables de entorno, nunca en el código.
Si falta una clave, la aplicación se detiene con un mensaje claro (no con un error raro
a mitad de una demo).
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

# Los tres proveedores hablan el mismo "idioma" (la API de Chat Completions de OpenAI).
# Cambiar de proveedor es cambiar base_url, clave y modelo: los endpoints no se tocan.
CATALOGO = {
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "clave": "GEMINI_API_KEY",
        "modelo_env": "GEMINI_MODEL",
        "modelo": "gemini-3.8-flash",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "clave": "GROQ_API_KEY",
        "modelo_env": "GROQ_MODEL",
        "modelo": "openai/gpt-oss-20b",
    },
    # Servidor local que imita a un proveedor (scripts/servidor_simulado.py).
    # Sirve para practicar errores 429 sin gastar cuota.
    "simulado": {
        "base_url": "http://127.0.0.1:8099/v1",
        "clave": None,
        "modelo_env": None,
        "modelo": "simulado-1",
    },
}


class ErrorConfiguracion(RuntimeError):
    """Falta o está mal una variable del .env."""


@dataclass(frozen=True)
class Proveedor:
    nombre: str
    base_url: str
    api_key: str
    modelo: str


@dataclass(frozen=True)
class Config:
    principal: Proveedor
    respaldo: Proveedor | None
    timeout_s: float
    max_tokens: int
    reintentos: int
    razonamiento: str | None  # "low" | "medium" | "high" | None


def _env(nombres: tuple[str, ...], defecto: str = "") -> str:
    """Primer valor NO vacío entre varios nombres de variable.

    Acepta los nombres del kit (LLM_PRINCIPAL, LLM_TIMEOUT_S...) y los de la plantilla
    de la clase 1 (LLM_PROVIDER, LLM_TIMEOUT_SECONDS...). Una línea vacía como
    «LLM_REINTENTOS=» cuenta como ausente y usa el valor por defecto.
    """
    for n in nombres:
        v = os.getenv(n, "").strip()
        if v:
            return v
    return defecto


def _numero(nombres: tuple[str, ...], defecto: str, tipo=float):
    v = _env(nombres, defecto)
    try:
        return tipo(v)
    except ValueError:
        raise ErrorConfiguracion(f"{nombres[0]} debe ser un número y en el .env dice «{v}».") from None


def _proveedor(nombre: str, modelo_rol: str | None = None) -> Proveedor:
    """modelo_rol: nombre de variable de la plantilla de la clase 1 según el papel
    del proveedor (LLM_MODEL para el principal, LLM_FALLBACK_MODEL para el respaldo)."""
    nombre = nombre.strip().lower()
    if nombre not in CATALOGO:
        raise ErrorConfiguracion(f"Proveedor desconocido: «{nombre}». Use gemini, groq o simulado.")
    c = CATALOGO[nombre]
    clave = "no-se-necesita"
    if c["clave"]:
        clave = os.getenv(c["clave"], "").strip()
        if not clave:
            raise ErrorConfiguracion(
                f"Falta {c['clave']} en el archivo .env. Copie .env.example como .env y pegue su clave."
            )
    nombres_modelo = tuple(n for n in (c["modelo_env"], modelo_rol) if n)
    modelo = _env(nombres_modelo) if nombres_modelo else ""
    return Proveedor(nombre, c["base_url"], clave, modelo or c["modelo"])


def cargar_config() -> Config:
    principal = _proveedor(_env(("LLM_PRINCIPAL", "LLM_PROVIDER"), "gemini"), "LLM_MODEL")
    nombre_respaldo = _env(("LLM_RESPALDO", "LLM_FALLBACK_PROVIDER"))
    respaldo = (_proveedor(nombre_respaldo, "LLM_FALLBACK_MODEL")
                if nombre_respaldo and nombre_respaldo != principal.nombre else None)
    razonamiento: str | None = _env(("LLM_RAZONAMIENTO",), "low").lower()
    if razonamiento in ("none", "no", "off"):
        razonamiento = None
    elif razonamiento not in ("low", "medium", "high"):
        raise ErrorConfiguracion(
            f"LLM_RAZONAMIENTO debe ser low, medium, high o none, y en el .env dice «{razonamiento}»."
        )
    if principal.nombre == "simulado":
        razonamiento = None
    return Config(
        principal=principal,
        respaldo=respaldo,
        timeout_s=_numero(("LLM_TIMEOUT_S", "LLM_TIMEOUT_SECONDS"), "30", float),
        max_tokens=_numero(("LLM_MAX_TOKENS", "LLM_MAX_OUTPUT_TOKENS"), "2048", int),
        reintentos=_numero(("LLM_REINTENTOS",), "3", int),
        razonamiento=razonamiento,
    )
