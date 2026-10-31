from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Perfil = Literal["conductor_particular", "conductor_profesional", "motociclista", "ciclista", "peaton"]
Dificultad = Literal["baja", "media", "alta"]
IdOpcion = Literal["A", "B", "C", "D"]

MARCA_FUERA_DE_DOMINIO = "FALTA"


class Estricto(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _largo(v: str, minimo: int, maximo: int, campo: str) -> str:
    if not minimo <= len(v.strip()) <= maximo:
        raise ValueError(f"{campo} debe tener entre {minimo} y {maximo} caracteres")
    return v.strip()


class SolicitudEscenario(Estricto):
    perfil: Perfil
    nivel_dificultad: Dificultad
    tema: str | None = Field(default=None, max_length=200)


class SolicitudEvaluacion(Estricto):
    id_escenario: str = Field(min_length=1, max_length=64)
    respuesta: IdOpcion


class SolicitudChat(Estricto):
    pregunta: str | None = Field(default=None, max_length=500)
    texto: str | None = Field(default=None, max_length=500)
    incluir_documento_envenenado_demo: bool = False

    def obtener_pregunta(self) -> str:
        q = (self.pregunta or self.texto or "").strip()
        if len(q) < 3:
            raise ValueError("La pregunta debe tener al menos 3 caracteres")
        return q


class OpcionEscenario(Estricto):
    id_opcion: IdOpcion
    texto: str
    es_correcta: bool

    @field_validator("texto")
    @classmethod
    def _texto(cls, v: str) -> str:
        return _largo(v, 5, 250, "texto")


class EscenarioVialSchema(Estricto):
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
            return self
        ids = [o.id_opcion for o in self.opciones]
        if sorted(ids) != ["A", "B", "C", "D"]:
            raise ValueError("opciones debe tener exactamente 4 elementos con id_opcion A, B, C y D")
        correctas = [o.id_opcion for o in self.opciones if o.es_correcta]
        if correctas != [self.respuesta_correcta]:
            raise ValueError("exactamente una opción debe tener es_correcta=true y coincidir con respuesta_correcta")
        return self


class Contravencion(Estricto):
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


class OpcionPublica(Estricto):
    id_opcion: IdOpcion
    texto: str


class EscenarioPublico(Estricto):
    id_escenario: str
    perfil: Perfil
    nivel_dificultad: Dificultad
    situacion: str
    opciones: list[OpcionPublica]
    aviso: str


class Sancion(Estricto):
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


class ProgresoUsuario(Estricto):
    usuario_id: str
    total_evaluados: int = 0
    aciertos: int = 0
    fallos: int = 0
    multas_acumuladas_usd: float = 0.0
    puntos_perdidos: float = 0.0
    dificultad_sugerida: Dificultad = "baja"
    historial: list[bool] = Field(default_factory=list)


class ResultadoEvaluacion(Estricto):
    id_escenario: str
    respuesta_usuario: IdOpcion
    es_correcta: bool
    respuesta_correcta: IdOpcion
    explicacion_educativa: str
    contravencion: ContravencionPublica
    sancion: Sancion
    progreso: ProgresoUsuario | None = None
    aviso: str
