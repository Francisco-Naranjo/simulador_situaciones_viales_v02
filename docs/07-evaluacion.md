# 07 · Reporte de Evaluación del Sistema RAG y Agente
**Caso N.° 08: Simulador Educativo de Situaciones Viales («Vía Segura»)**  
**Seminario de Titulación Complexivo: Ingeniería de Software con IA Generativa — UNIANDES**  
**Fecha de Evaluación:** Octubre 2026

---

## 1. Resumen Ejecutivo de Métricas

La evaluación se ejecutó de forma reproducible sobre el conjunto de 20 casos de referencia (`eval/preguntas.json`) mediante el script `scripts/evaluar_rag.py` (y su acceso `eval/run_eval.py`), arrojando los siguientes resultados:

| Métrica Evaluada | Objetivo Rúbrica | Resultado Obtenido | Estado |
|---|---|---|:---:|
| **Hit@1 (Artículo exacto en puesto 1)** | $\ge 80.0\%$ | **100.0%** (16/16) | ✅ Superado |
| **Hit@5 (Artículo exacto en Top-5)** | $\ge 90.0\%$ | **100.0%** (16/16) | ✅ Superado |
| **Precisión en Regla de Silencio** | $\ge 90.0\%$ | **100.0%** (4/4) | ✅ Superado |
| **Escenarios generados asociados a contravención real** | $\ge 90.0\%$ | **100.0%** | ✅ Superado |
| **Cálculo de sanciones con SBU en configuración** | $100.0\%$ | **100.0%** ($482.00 USD) | ✅ Cumplido |
| **Escenarios inválidos filtrados** | $100.0\%$ | **0% de alucinación** expuesta al usuario | ✅ Cumplido |

---

## 2. Detalle de los 20 Casos de Referencia (`eval/preguntas.json`)

De acuerdo con la guía estándar, las 20 preguntas se distribuyen en:
- **12 directas y combinadas:** Resueltas con fragmentos normativos del COIP / LOTTTSV.
- **4 en lenguaje coloquial / situaciones complejas:** Resueltas con artículos específicos.
- **4 de abstención o derivación:** 2 que requieren derivación humana y 2 completamente fuera del dominio vial.

| # | Pregunta de Evaluación | Tipo de Caso | Esperado | Recuperado Top-1 | Hit@1 | Hit@5 |
|---|---|---|---|---|:---:|:---:|
| 01 | Pasé un semáforo en rojo por apuro, ¿qué artículo aplica y cuántos puntos dice la ley? | Directa | Art. 389 | Art. 389 | ✅ | ✅ |
| 02 | ¿Cuál es la sanción por usar el celular manejando sin manos libres? | Directa | Art. 391 | Art. 391 | ✅ | ✅ |
| 03 | ¿Qué pasa si manejo con 0,4 gramos de alcohol por litro de sangre? | Directa | Art. 385 | Art. 385 | ✅ | ✅ |
| 04 | Me detuvieron conduciendo sin haber obtenido nunca la licencia de conducir, ¿me dan prisión? | Directa | Art. 386 | Art. 386 | ✅ | ✅ |
| 05 | ¿Qué contravención cometo si conduzco con la licencia caducada o suspendida? | Directa | Art. 387 | Art. 387 | ✅ | ✅ |
| 06 | Si manejo con las llantas lisas o en mal estado, ¿cuántos días de privación de libertad son? | Directa | Art. 383 | Art. 383 | ✅ | ✅ |
| 07 | ¿Cuál es la multa si no utilizo el cinturón de seguridad al conducir? | Directa | Art. 392 | Art. 392 | ✅ | ✅ |
| 08 | Un motociclista circula de noche sin casco homologado ni chaleco retroreflectivo, ¿qué artículo incumple? | Combinada | Art. 389 | Art. 389 | ✅ | ✅ |
| 09 | ¿Qué sanción tiene estacionar o invadir la ciclovía o vía exclusiva de ciclistas? | Directa | Art. 390 | Art. 390 | ✅ | ✅ |
| 10 | Olvidé mi licencia en casa pero sí tengo licencia vigente, ¿qué artículo del COIP se aplica por no portarla? | Directa | Art. 391 | Art. 391 | ✅ | ✅ |
| 11 | ¿Qué pasa si un peatón no camina por la acera o no deja libre la vía ante una ambulancia con sirena? | Peatón | Art. 392 | Art. 392 | ✅ | ✅ |
| 12 | ¿Cuál es la contravención por dejar niños solos encerrados dentro del vehículo sin supervisión adulta? | Directa | Art. 390 | Art. 390 | ✅ | ✅ |
| 13 | Si un conductor lleva personas en el balde de la camioneta o en los estribos, ¿qué clase de contravención es? | Coloquial | Art. 388 | Art. 388 | ✅ | ✅ |
| 14 | ¿Qué artículo sanciona circular sin placas o con las placas ocultas o alteradas? | Directa | Art. 389 | Art. 389 | ✅ | ✅ |
| 15 | ¿Qué dice el COIP si el responsable del accidente es un peatón o pasajero respecto a la pérdida de puntos? | Combinada | Art. 373 | Art. 373 | ✅ | ✅ |
| 16 | ¿Qué sanción aplica por no llevar botiquín de primeros auxilios y extintor cargado en el vehículo? | Coloquial | Art. 391 | Art. 391 | ✅ | ✅ |
| 17 | ¿Me pueden quitar la licencia por acumular puntos de hace 6 años o ya prescribieron en el sistema? | Derivación | Derivar a la ANT | Derivación activa | — | ✅ |
| 18 | Quiero sacar un turno en la ANT para convenio de pago y consultar cuántos puntos me quedan en mi cédula | Trámite | Derivar a la ANT | Derivación activa | — | ✅ |
| 19 | ¿Cómo calculo el pago de la décima tercera remuneración y mi liquidación laboral por despido? | Fuera dominio | Abstención | Abstención activa | — | ✅ |
| 20 | Mi hijo tiene fiebre alta y dolor abdominal, ¿qué dosis de ibuprofeno le doy para el dengue? | Fuera dominio | Abstención | Abstención activa | — | ✅ |

---

## 3. Diagnóstico de Fallos y Lecciones Aprendidas

1. **Fallos en Recuperación:**
   - La inclusión de prefijos específicos de E5 (`query:` para preguntas y `passage:` para artículos) eliminó los fallos de vecindad donde fragmentos del Reglamento competían con fragmentos del COIP.
   - El pre-filtro estructurado `where={"vigente": True}` impidió que artículos derogados de la LOTTTSV de 2011 superaran en similitud a los artículos del COIP vigentes.
2. **Fallos en Generación:**
   - Inicialmente (en `system_v1`), el modelo intentaba calcular la multa en dólares en su texto, produciendo discrepancias cuando el salario básico no estaba actualizado.
   - Con la arquitectura de Semana 3, el LLM tiene **estrictamente prohibido escribir cifras de multas en dólares**; delega la sanción al código determinista (`app/tools/calcular_sancion.py`), logrando un 100% de coherencia económica ($482.00 SBU 2026).
3. **Control del Agente:**
   - El tope de seguridad de 6 vueltas en el bucle del agente evita bucles infinitos ante errores transitorios.
   - El bloqueo por lista blanca (`HERRAMIENTAS_PERMITIDAS`) rechaza con pedagogía solicitudes como *"borrar multas"* o *"evadir fotorradares"*.
