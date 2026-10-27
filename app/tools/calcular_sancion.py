"""Herramienta determinista: calcular_sancion(porcentaje_sbu).

Principio 3: lo que se calcula, lo calcula el código. El modelo JAMÁS calcula multas ni puntos.
Se usa Decimal con redondeo comercial (ROUND_HALF_UP) para evitar errores de coma flotante
(0.1 + 0.2 != 0.3) en montos de dinero.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from app.parametros import cargar_parametros
from app.schemas import Contravencion, Sancion


def calcular_multa(porcentaje_sbu: float, sbu_usd: float) -> Decimal:
    """Multa en USD = porcentaje del SBU. Ej.: 30 % de 482.00 = 144.60 (o 200 % en Art. 386 inc. 2)."""
    if not (0 <= porcentaje_sbu <= 100 or porcentaje_sbu == 200):
        raise ValueError("porcentaje_sbu debe estar entre 0 y 100 (o 200 para Art. 386 inc. 2)")
    if sbu_usd <= 0:
        raise ValueError("sbu_usd debe ser positivo")
    multa = Decimal(str(sbu_usd)) * Decimal(str(porcentaje_sbu)) / Decimal(100)
    return multa.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calcular_sancion(contravencion: Contravencion, parametros: dict | None = None) -> Sancion:
    """Sanción completa de una contravención de la tabla, con el SBU leído de configuración."""
    p = parametros or cargar_parametros()
    return Sancion(
        porcentaje_sbu=contravencion.porcentaje_sbu,
        sbu_usd=float(p["sbu_usd"]),
        multa_usd=float(calcular_multa(contravencion.porcentaje_sbu, p["sbu_usd"])),
        puntos_reducidos=contravencion.puntos_reducidos,
        puntos_aplicables=contravencion.puntos_aplicables,
        pena_adicional=contravencion.pena_adicional,
        dias_privacion_libertad=contravencion.dias_privacion_libertad,
        fuente_sbu=p.get("sbu_fuente", "config/parametros.json"),
    )
