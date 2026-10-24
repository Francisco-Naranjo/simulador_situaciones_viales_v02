"""Parámetros que cambian con el tiempo (SBU, límites, avisos): viven en config/parametros.json.

Se leen en CADA llamada (el archivo es diminuto): así, si se cambia el salario básico en
configuración, la siguiente sanción ya usa el valor nuevo sin reiniciar el servidor
(prueba mínima del caso 08: «cambio del salario básico en configuración»).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
RUTA_PARAMETROS = Path(os.getenv("PARAMETROS_PATH", RAIZ / "config" / "parametros.json"))


def cargar_parametros(ruta: Path | None = None) -> dict:
    datos = json.loads(Path(ruta or RUTA_PARAMETROS).read_text(encoding="utf-8"))
    if not isinstance(datos.get("sbu_usd"), (int, float)) or datos["sbu_usd"] <= 0:
        raise ValueError("config/parametros.json: sbu_usd debe ser un número positivo")
    return datos
