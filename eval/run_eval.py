from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from scripts.evaluar_rag import evaluar

if __name__ == "__main__":
    res = evaluar()
    print("=== Evaluacion RAG · Caso 08: Via Segura ===")
    print(f"[OK] Total preguntas evaluadas: {res['total_preguntas']} ({res['preguntas_con_fuente']} con fuente + {res['preguntas_abstencion']} abstencion)")
    print(f"[OK] Hit@1: {res['hit_at_1']*100:.1f}% | Hit@5: {res['hit_at_5']*100:.1f}%")
    print(f"[OK] Precision en Regla de Silencio (abstencion/derivacion): {res['precision_silencio']*100:.1f}%")
    for d in res["detalle"]:
        if "hit_5" in d:
            marca = "[OK]" if d["hit_5"] else "[FALLO]"
            print(f"  #{d['id']:02d} {marca} esperado={d['esperado']} -> top5={d['recuperados'][:3]}")
        else:
            marca = "[OK]" if d["abstencion_correcta"] else "[FALLO]"
            print(f"  #{d['id']:02d} {marca} abstencion ({d['tipo']}) -> abstuvo={d['abstencion_correcta']}")
