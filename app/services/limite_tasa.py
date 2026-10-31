from __future__ import annotations

import math
import threading
import time
from typing import Callable


class LimitadorTasa:
    def __init__(self, capacidad: float, recarga_por_segundo: float,
                 reloj: Callable[[], float] = time.monotonic, max_claves: int = 10_000):
        self.capacidad, self.recarga, self.reloj, self.max_claves = capacidad, recarga_por_segundo, reloj, max_claves
        self._baldes: dict[str, tuple[float, float]] = {}
        self._candado = threading.Lock()

    def consumir(self, clave: str) -> float:
        with self._candado:
            ahora = self.reloj()
            fichas, antes = self._baldes.get(clave, (self.capacidad, ahora))
            fichas = min(self.capacidad, fichas + (ahora - antes) * self.recarga)
            if fichas >= 1:
                if len(self._baldes) >= self.max_claves and clave not in self._baldes:
                    self._baldes.clear()
                self._baldes[clave] = (fichas - 1, ahora)
                return 0.0
            self._baldes[clave] = (fichas, ahora)
            return max(1.0, math.ceil((1 - fichas) / self.recarga))
