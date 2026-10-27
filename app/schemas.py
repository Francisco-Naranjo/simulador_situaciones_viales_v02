"""Esquemas (Pydantic) de lo que ENTRA al sistema, de lo que el MODELO debe devolver
y de lo que el backend entrega al frontend. Caso 08 · Simulador de situaciones viales.

Reglas para que el esquema funcione con el modo estricto de Gemini y Groq (kit de la semana 2):
  - extra="forbid" en cada modelo (no se aceptan campos inventados · OWASP LLM05).
  - Todos los campos de la salida del modelo son obligatorios.
  - Los límites de longitud y cantidad NO van en el esquema JSON (minLength, minItems…):
    van en validadores de Python. El esquema GUÍA al modelo; la validación la hace el código.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Perfil = Literal["conductor_particular", "conductor_profesional", "motociclista", "ciclista", "peaton"]
Dificultad = Literal["baja", "media", "alta"]
IdOpcion = Literal["A", "B", "C", "D"]

# Marca de abstención: el prompt pide al modelo usarla en id_contravencion_asociada
# cuando la solicitud está fuera del dominio vial (principio «lo que no sabe, lo dice»).
MARCA_FUERA_DE_DOMINIO = "FALTA"


class Estricto(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _largo(v: str, minimo: int, maximo: int, campo: str) -> str:
    if not minimo <= len(v.strip()) <= maximo:
        raise ValueError(f"{campo} debe tener entre {minimo} y {maximo} caracteres")
    return v.strip()


# ====================================================================== entrada
class SolicitudEscenario(Estricto):
    """Lo que envía el usuario. Todo acotado: el texto libre (tema) tiene límite de tamaño
    (defensa contra consumo excesivo, OWASP LLM10) y se trata como dato, no como orden."""
    perfil: Perfil
    nivel_dificultad: Dificultad
    tema: str | None = Field(default=None, max_length=200,
                             description="Opcional: tema vial a practicar (p. ej. «velocidad», «paso cebra»)")


class SolicitudEvaluacion(Estricto):
    id_escenario: str = Field(min_length=1, max_length=64)
    respuesta: IdOpcion  # cualquier valor fuera de A-D se rechaza con 422 antes de evaluar


# ====================================================================== salida del modelo
class OpcionEscenario(Estricto):
    id_opcion: IdOpcion
    texto: str
    es_correcta: bool

    @field_validator("texto")
    @classmethod
    def _texto(cls, v: str) -> str:
        return _largo(v, 5, 250, "texto")


class EscenarioVialSchema(Estricto):
    """Contrato del Documento Maestro (sección 3). Lo que el MODELO debe devolver."""
    id_escenario: str
    perfil: Perfil
    nivel_dificultad: Dificultad
    situacion: str
    opciones: list[OpcionEscenario]
    respuesta_correcta: IdOpcion
    id_contravencion_asociada: str
    articulo_norma: str
    explicacion_educativa: str

    @field_validator("situacion")
    @classmethod
    def _situacion(cls, v: str) -> str:
        return _largo(v, 20, 1000, "situacion")

    @field_validator("explicacion_educativa")
    @classmethod
    def _explicacion(cls, v: str) -> str:
        return _largo(v, 10, 1200, "explicacion_educativa")

    @model_validator(mode="after")
    def _coherencia(self) -> "EscenarioVialSchema":
        if self.id_contravencion_asociada.strip().upper() == MARCA_FUERA_DE_DOMINIO:
            return self  # abstención: el resto del contenido no se usa
        ids = [o.id_opcion for o in self.opciones]
        if sorted(ids) != ["A", "B", "C", "D"]:
            raise ValueError("opciones debe tener exactamente 4 elementos con id_opcion A, B, C y D")
        correctas = [o.id_opcion for o in self.opciones if o.es_correcta]
        if correctas != [self.respuesta_correcta]:
            raise ValueError("exactamente una opción debe tener es_correcta=true y coincidir con respuesta_correcta")
        return self


# ====================================================================== tabla canónica
class Contravencion(Estricto):
    """Un registro de data/raw/contravenciones_lotttsv.json (única fuente de verdad)."""
    id_contravencion: str
    codigo_csv: str | None = None
    clase: str
    articulo: str
    norma: str
    descripcion_infraccion: str
    texto_literal_coip: str | None = None
    porcentaje_sbu: float = Field(ge=0, le=200)
    puntos_reducidos: float = Field(ge=0, le=30)
    puntos_aplicables: float | None = Field(default=None, ge=0, le=30)
    pena_adicional: str | None = None
    perfiles_aplicables: list[Perfil] = Field(min_length=1)
    dias_privacion_libertad: int = Field(default=0, ge=0)
    fuente_url: str | None = None


# ====================================================================== respuestas del API
class OpcionPublica(Estricto):
    id_opcion: IdOpcion
    texto: str


class EscenarioPublico(Estricto):
    """Lo que ve el usuario ANTES de responder: sin la respuesta correcta ni la explicación."""
    id_escenario: str
    perfil: Perfil
    nivel_dificultad: Dificultad
    situacion: str
    opciones: list[OpcionPublica]
    aviso: str


class Sancion(Estricto):
    """Calculada SIEMPRE por código (app/tools/calcular_sancion.py), nunca por el modelo."""
    porcentaje_sbu: float
    sbu_usd: float
    multa_usd: float
    puntos_reducidos: float
    puntos_aplicables: float | None = None
    pena_adicional: str | None = None
    dias_privacion_libertad: int
    fuente_sbu: str


class ContravencionPublica(Estricto):
    id_contravencion: str
    codigo_csv: str | None = None
    clase: str
    articulo: str
    norma: str
    descripcion_infraccion: str
    texto_literal_coip: str | None = None


class ResultadoEvaluacion(Estricto):
    id_escenario: str
    respuesta_usuario: IdOpcion
    es_correcta: bool
    respuesta_correcta: IdOpcion
    explicacion_educativa: str
    contravencion: ContravencionPublica
    sancion: Sancion
    aviso: str
