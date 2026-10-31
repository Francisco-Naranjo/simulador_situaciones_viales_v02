from __future__ import annotations

from app.schemas import Dificultad, ProgresoUsuario

_PROGRESO: dict[str, ProgresoUsuario] = {}


def ajustar_dificultad(historial: list[bool]) -> Dificultad:
    if not historial:
        return "baja"
    ultimos = historial[-3:]
    if len(ultimos) >= 3 and all(ultimos):
        return "alta"
    if len(ultimos) >= 2 and all(ultimos[-2:]):
        return "media"
    if len(ultimos) >= 2 and not any(ultimos[-2:]):
        return "baja"
    return "media" if historial.count(True) > len(historial) // 2 else "baja"


def registrar_progreso(
    usuario_id: str,
    es_correcta: bool,
    multa_usd: float = 0.0,
    puntos_reducidos: float = 0.0,
) -> ProgresoUsuario:
    p = _PROGRESO.setdefault(usuario_id, ProgresoUsuario(usuario_id=usuario_id))
    p.total_evaluados += 1
    if es_correcta:
        p.aciertos += 1
    else:
        p.fallos += 1
        p.multas_acumuladas_usd = round(p.multas_acumuladas_usd + multa_usd, 2)
        p.puntos_perdidos = round(p.puntos_perdidos + puntos_reducidos, 1)
    p.historial.append(es_correcta)
    p.dificultad_sugerida = ajustar_dificultad(p.historial)
    return p


def obtener_progreso(usuario_id: str) -> ProgresoUsuario:
    return _PROGRESO.get(usuario_id, ProgresoUsuario(usuario_id=usuario_id))


def reiniciar_progreso(usuario_id: str) -> None:
    _PROGRESO.pop(usuario_id, None)
