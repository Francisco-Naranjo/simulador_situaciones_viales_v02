from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from scripts.evaluar_rag import (  # noqa: E402
    RUTA_PREGUNTAS,
    RUTA_PREGUNTAS_FINALES,
    RUTA_RESULTADOS,
    RUTA_RESULTADOS_FINALES,
    evaluar,
    imprimir_reporte,
)

if __name__ == "__main__":
    res_base = evaluar(RUTA_PREGUNTAS, RUTA_RESULTADOS)
    imprimir_reporte("Evaluacion RAG · Banco Referencia", res_base)
    if RUTA_PREGUNTAS_FINALES.exists():
        print()
        res_final = evaluar(RUTA_PREGUNTAS_FINALES, RUTA_RESULTADOS_FINALES)
        imprimir_reporte("Evaluacion RAG · Banco Independiente Final", res_final)
