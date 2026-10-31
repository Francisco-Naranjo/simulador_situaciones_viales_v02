# 07 · Reporte de Evaluación del Sistema RAG y Agente
**Caso N.° 08: Simulador Educativo de Situaciones Viales («Vía Segura»)**  
**Seminario de Titulación Complexivo: Ingeniería de Software con IA Generativa — UNIANDES**  
**Fecha de Evaluación:** Octubre 2026

---

## 1. Resumen Ejecutivo de Métricas

La evaluación se ejecutó de forma reproducible mediante `eval/run_eval.py` (`scripts/evaluar_rag.py`) sobre dos bancos de pruebas de 20 casos cada uno:
1. **Banco de Referencia (`eval/preguntas.json`):** 20 casos base (16 con fuente normativa + 4 de abstención/derivación).
2. **Banco Independiente de Validación (`eval/preguntas_finales.json`):** 20 casos nuevos no vistos durante el ajuste inicial (16 con fuente normativa + 4 de abstención/derivación), sin números de artículos en el tesauro ni patrones ad-hoc.

| Métrica Evaluada | Objetivo Rúbrica | Banco Referencia (`preguntas.json`) | Banco Independiente (`preguntas_finales.json`) | Estado |
|---|---|:---:|:---:|:---:|
| **Hit@1 (Artículo exacto en puesto 1)** | $\ge 80.0\%$ | **87.5%** (14/16) | **87.5%** (14/16) | ✅ Superado |
| **Hit@5 (Artículo exacto en Top-5)** | $\ge 90.0\%$ | **100.0%** (16/16) | **100.0%** (16/16) | ✅ Superado |
| **Precisión en Regla de Silencio** | $\ge 90.0\%$ | **100.0%** (4/4) | **100.0%** (4/4) | ✅ Superado |
| **Escenarios asociados a contravención real** | $\ge 90.0\%$ | **100.0%** | **100.0%** | ✅ Superado |
| **Cálculo de sanciones con SBU en configuración** | $100.0\%$ | **100.0%** ($482.00 USD) | **100.0%** ($482.00 USD) | ✅ Cumplido |
| **Tool Calling con Esquemas Pydantic y Rol `tool`** | $100.0\%$ | **100.0%** | **100.0%** | ✅ Cumplido |

---

## 2. Detalle del Banco de Referencia (`eval/preguntas.json`)

| # | Pregunta de Evaluación | Tipo de Caso | Esperado | Recuperado Top-1 | Hit@1 | Hit@5 |
|---|---|---|---|---|:---:|:---:|
| 01 | Pasé un semáforo en rojo por apuro, ¿qué artículo aplica y cuántos puntos dice la ley? | Directa | Art. 389 | Art. 389 | ✅ | ✅ |
| 02 | ¿Cuál es la sanción por usar el celular manejando sin manos libres? | Directa | Art. 391 | Art. 391 | ✅ | ✅ |
| 03 | ¿Qué pasa si manejo con 0,4 gramos de alcohol por litro de sangre? | Directa | Art. 385 | Art. 385 | ✅ | ✅ |
| 04 | Me detuvieron conduciendo sin haber obtenido nunca la licencia de conducir, ¿me dan prisión? | Directa | Art. 386 | Art. 386 | ✅ | ✅ |
| 05 | ¿Qué contravención cometo si conduzco con la licencia caducada o suspendida? | Directa | Art. 387 | Art. 387 | ✅ | ✅ |
| 06 | Si manejo con las llantas lisas o en mal estado, ¿cuántos días de privación de libertad son? | Directa | Art. 383 | Art. 383 | ✅ | ✅ |
| 07 | ¿Cuál es la multa si no utilizo el cinturón de seguridad al conducir? | Directa | Art. 392 | Art. 389 (392 en Top-2) | — | ✅ |
| 08 | Un motociclista circula de noche sin casco homologado ni chaleco retroreflectivo, ¿qué artículo incumple? | Combinada | Art. 389 | Art. 389 | ✅ | ✅ |
| 09 | ¿Qué sanción tiene estacionar o invadir la ciclovía o vía exclusiva de ciclistas? | Directa | Art. 390 | Art. 391 (390 en Top-2) | — | ✅ |
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

## 3. Banco Independiente de Validación (`eval/preguntas_finales.json`)

El segundo banco evalúa 20 consultas independientes sobre artículos distintos y redacciones no vistas (incluyendo Arts. 371, 374, 376, 384, 386, 387, 388, 389, 390, 391 y 392 del COIP, además de 4 casos nuevos de derivación y fuera de dominio), obteniendo **87.5% en Hit@1**, **100.0% en Hit@5** y **100.0% en Regla de Silencio**, almacenados en `eval/resultados_finales.json`.

---

## 4. Diagnóstico Técnico y Lecciones Aprendidas

1. **Recuperación Vectorial Real sin Sesgo:**
   - Se indexaron los 641 artículos en `chroma_db/chroma.sqlite3` con `SentenceTransformer("intfloat/multilingual-e5-small")`.
   - Se eliminaron del tesauro todas las referencias directas a números de artículos y se implementó normalización por longitud documental para evitar que glosarios extensos del Reglamento desplacen a los artículos punitivos del COIP.
2. **Tool Calling con Esquemas Pydantic y Rol `tool`:**
   - El agente (`app/services/agente.py`) define esquemas Pydantic estrictos (`extra="forbid"`) para cada herramienta, los expone en formato `tools` de OpenAI, despacha las llamadas mediante `despachar_herramienta` y registra los mensajes `assistant` (`tool_calls`) y `tool` (`tool_call_id`) en un ciclo controlado con tope de 6 vueltas.
3. **Integración Continua (CI):**
   - El flujo `.github/workflows/ci.yml` ejecuta automáticamente en cada push/PR las pruebas unitarias (`pytest`), la evaluación RAG sobre ambos bancos (`python eval/run_eval.py`) y la compilación del frontend React (`npm run build`).
