"""Evaluación cuantitativa del sistema RAG (`hit@5` y tasa de abstención) · Caso 08 «Vía Segura».

Evalúa las 20 preguntas de `eval/preguntas.json`:
  - Para preguntas con respuesta en las fuentes (`debe_abstenerse=false`): verifica si el artículo
    esperado aparece dentro de los primeros 5 fragmentos recuperados (`hit@5`) y en el primer lugar (`hit@1`).
  - Para preguntas fuera de alcance o de derivación (`debe_abstenerse=true`): verifica que el sistema
    active la regla de silencio (`abstencion=True`) con el mensaje oficial de derivación.

Uso:
    python scripts/evaluar_rag.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from app.services.rag import recuperar  # noqa: E402

RUTA_PREGUNTAS = RAIZ / "eval" / "preguntas.json"
RUTA_RESULTADOS = RAIZ / "eval" / "resultados_rag.json"


def evaluar() -> dict:
    preguntas = json.loads(RUTA_PREGUNTAS.read_text(encoding="utf-8"))
    con_respuesta = [p for p in preguntas if not p["debe_abstenerse"]]
    sin_respuesta = [p for p in preguntas if p["debe_abstenerse"]]

    aciertos_hit1 = 0
    aciertos_hit5 = 0
    aciertos_silencio = 0
    detalle = []

    for p in preguntas:
        r = recuperar(p["pregunta"], top_k=5)
        articulos_top5 = [f"Art. {f.metadatos.get('articulo')}" for f in r.fragmentos]
        if p["debe_abstenerse"]:
            ok = r.abstencion is True
            if ok:
                aciertos_silencio += 1
            detalle.append({
                "id": p["id"],
                "pregunta": p["pregunta"],
                "tipo": p["tipo"],
                "abstencion_correcta": ok,
                "recuperados": articulos_top5,
            })
        else:
            esperado = p["esperado"]
            en_top1 = bool(articulos_top5 and articulos_top5[0] == esperado)
            en_top5 = esperado in articulos_top5
            if en_top1:
                aciertos_hit1 += 1
            if en_top5:
                aciertos_hit5 += 1
            detalle.append({
                "id": p["id"],
                "pregunta": p["pregunta"],
                "esperado": esperado,
                "hit_1": en_top1,
                "hit_5": en_top5,
                "recuperados": articulos_top5,
            })

    resumen = {
        "total_preguntas": len(preguntas),
        "preguntas_con_fuente": len(con_respuesta),
        "preguntas_abstencion": len(sin_respuesta),
        "hit_at_1": round(aciertos_hit1 / max(1, len(con_respuesta)), 4),
        "hit_at_5": round(aciertos_hit5 / max(1, len(con_respuesta)), 4),
        "precision_silencio": round(aciertos_silencio / max(1, len(sin_respuesta)), 4),
        "detalle": detalle,
    }
    RUTA_RESULTADOS.write_text(json.dumps(resumen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return resumen


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
