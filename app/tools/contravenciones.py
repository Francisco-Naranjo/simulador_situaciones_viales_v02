from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from app.schemas import MARCA_FUERA_DE_DOMINIO, Contravencion, EscenarioVialSchema

RAIZ = Path(__file__).resolve().parent.parent.parent
RUTA_TABLA = Path(os.getenv("CONTRAVENCIONES_PATH", RAIZ / "data" / "raw" / "contravenciones_lotttsv.json"))


class EscenarioInvalido(ValueError):
    pass


class FueraDeDominio(ValueError):
    pass


@lru_cache
def cargar_tabla(ruta: str | None = None) -> dict[str, Contravencion]:
    registros = json.loads(Path(ruta or RUTA_TABLA).read_text(encoding="utf-8"))
    tabla = {}
    for r in registros:
        c = Contravencion.model_validate(r)
        if c.id_contravencion in tabla:
            raise ValueError(f"id_contravencion duplicado en la tabla: {c.id_contravencion}")
        tabla[c.id_contravencion] = c
    return tabla


def candidatas(perfil: str, tabla: dict[str, Contravencion] | None = None) -> list[Contravencion]:
    return [c for c in (tabla or cargar_tabla()).values() if perfil in c.perfiles_aplicables]


def validar_escenario(
    esc: EscenarioVialSchema,
    perfil: str,
    nivel: str,
    tabla: dict[str, Contravencion] | None = None,
) -> Contravencion:
    tabla = tabla or cargar_tabla()
    id_buscado = esc.id_contravencion_asociada.strip()
    if id_buscado.upper() == MARCA_FUERA_DE_DOMINIO:
        raise FueraDeDominio()
    c = tabla.get(id_buscado) or next((item for item in tabla.values() if item.codigo_csv == id_buscado), None)
    if c is None:
        raise EscenarioInvalido(f"contravención inexistente en la tabla: {esc.id_contravencion_asociada!r}")
    if perfil not in c.perfiles_aplicables:
        raise EscenarioInvalido(f"{c.id_contravencion} no aplica al perfil {perfil}")
    if esc.perfil != perfil or esc.nivel_dificultad != nivel:
        raise EscenarioInvalido("el perfil o la dificultad no coinciden con la solicitud")
    return c
