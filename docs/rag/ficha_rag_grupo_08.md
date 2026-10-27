# Ficha de RAG · Grupo 8 · Simulador educativo de contravenciones viales

Integrantes: Equipo Grupo 08 · Carrera de Software UNIANDES
Fecha: 2026-10-26
Avance: 100 % (Fuentes, Corte, Etiquetas, Preguntas reales, Regla de silencio)

## Objetivo del RAG
Generar escenarios de tránsito, evaluar la respuesta del estudiante citando el artículo del COIP / LOTTTSV y calcular la sanción en código con el salario básico en configuración (`config/parametros.json`).

## 1. Fuentes
| Fuente | Dónde | Archivo en data/raw | Fecha/versión | Estado |
|---|---|---|---|---|
| COIP · Capítulo Octavo: Infracciones de Tránsito (Arts. 371–392) y LOTTTSV | Registro Oficial / ant.gob.ec | `AMT-COIP-CAPITULO-TRANSITO.pdf` | 2021-08 (RO 512) | descargada |
| Reglamento a la LOTTTSV | Registro Oficial Suplemento 731 | `REGLAMENTO_A_LA_LEY_DE_TRANSPORTE_TERRESTRE_TRANSITO_Y_SEGURIDAD_VIAL.pdf` | 2012-06 | descargada |
| Salario básico unificado 2026 | Ministerio del Trabajo | `config/parametros.json` (`sbu_usd: 482.00`) | 2026-01 | descargada |
| Tabla verificada de 90 contravenciones (COIP arts. 386–392) | Contraste propio contra PDF oficial | `data/tabla_contravenciones.csv` / `data/raw/contravenciones_lotttsv.json` | 2026-10 | descargada |

## 2. Estrategia de corte
Por artículo (`(?=Art\.\s*\d+\.-)` con validación de cabecera `/^Art\.\s*\d+/`). Cada retroalimentación del simulador cita el artículo exacto de la contravención. Los puntos y el porcentaje del SBU están en el artículo; el valor en dólares lo calcula el código determinista (`app/tools/calcular_sancion.py`). Resultado en `scripts/ingest.py`: **641 artículos indexados y 0 fragmentos huérfanos**.

## 3. Etiquetas (metadatos)
| Campo | Ejemplo del grupo | Para qué |
|---|---|---|
| `documento` | `COIP` | Cita verificable y prioridad jerárquica |
| `articulo` | `389` | Cita exacta mostrada al estudiante |
| `clase` | `cuarta` | Ajustar dificultad y filtrar contravenciones |
| `puntos` | `6` (`puntos_aplicables`: `0` según RO 512-2021) | Dato estructurado para la retroalimentación |
| `vigente` | `true` | Excluir artículos derogados de la LOTTTSV 2011 antes del `top-k` |

## 4. Preguntas de evaluación (eval/preguntas.json)
| # | Pregunta | Esperado | Tipo |
|---|---|---|---|
| 1 | Pasé un semáforo en rojo por apuro, ¿qué artículo aplica y cuántos puntos dice la ley? | Art. 389 | Tiene respuesta en las fuentes |
| 2 | ¿Cuál es la sanción por usar el celular manejando sin manos libres? | Art. 391 | Tiene respuesta en las fuentes |
| 3 | ¿Qué pasa si manejo con 0,4 gramos de alcohol por litro de sangre? | Art. 385 | Tiene respuesta en las fuentes |
| 4 | Me detuvieron conduciendo sin haber obtenido nunca la licencia de conducir, ¿me dan prisión? | Art. 386 | Tiene respuesta en las fuentes |
| 5 | ¿Qué contravención cometo si conduzco con la licencia caducada o suspendida? | Art. 387 | Tiene respuesta en las fuentes |
| 6 | Si manejo con las llantas lisas o en mal estado, ¿cuántos días de privación de libertad son? | Art. 383 | Tiene respuesta en las fuentes |
| 7 | ¿Cuál es la multa si no utilizo el cinturón de seguridad al conducir? | Art. 392 | Tiene respuesta en las fuentes |
| 8 | Un motociclista circula de noche sin casco homologado ni chaleco retroreflectivo, ¿qué artículo incumple? | Art. 389 | Tiene respuesta en las fuentes |
| 9 | ¿Qué sanción tiene estacionar o invadir la ciclovía o vía exclusiva de ciclistas? | Art. 390 | Tiene respuesta en las fuentes |
| 10 | Olvidé mi licencia en casa pero sí tengo licencia vigente, ¿qué artículo del COIP se aplica por no portarla? | Art. 391 | Tiene respuesta en las fuentes |
| 11 | ¿Qué pasa si un peatón no camina por la acera o no deja libre la vía ante una ambulancia con sirena? | Art. 392 | Tiene respuesta en las fuentes |
| 12 | ¿Cuál es la contravención por dejar niños solos encerrados dentro del vehículo sin supervisión adulta? | Art. 390 | Tiene respuesta en las fuentes |
| 13 | Si un conductor lleva personas en el balde de la camioneta o en los estribos, ¿qué clase de contravención es? | Art. 388 | Tiene respuesta en las fuentes |
| 14 | ¿Qué artículo sanciona circular sin placas o con las placas ocultas o alteradas? | Art. 389 | Tiene respuesta en las fuentes |
| 15 | ¿Qué dice el COIP si el responsable del accidente es un peatón o pasajero respecto a la pérdida de puntos? | Art. 373 | Tiene respuesta en las fuentes |
| 16 | ¿Qué sanción aplica por no llevar botiquín de primeros auxilios y extintor cargado en el vehículo? | Art. 391 | Tiene respuesta en las fuentes |
| 17 | ¿Me pueden quitar la licencia por acumular puntos de hace 6 años o ya prescribieron en el sistema? | — | Requiere derivar a una persona |
| 18 | Quiero sacar un turno en la ANT para convenio de pago y consultar cuántos puntos me quedan en mi cédula | — | Requiere derivar a una persona |
| 19 | ¿Cómo calculo el pago de la décima tercera remuneración y mi liquidación laboral por despido? | — | No está en las fuentes (debe abstenerse) |
| 20 | Mi hijo tiene fiebre alta y dolor abdominal, ¿qué dosis de ibuprofeno le doy para el dengue? | — | No está en las fuentes (debe abstenerse) |

## 5. Regla de silencio
Mensaje de abstención: La normativa que tengo cargada (COIP, LOTTTSV y su Reglamento) no responde esta pregunta o requiere verificación administrativa. Le recomiendo consultar directamente a la Agencia Nacional de Tránsito (ANT).

## Error que debemos evitar
Guardar el valor en dólares de la multa dentro del fragmento: el salario básico cambia cada enero y el sistema cita cifras viejas.

## Reto para avanzados
Validar cada escenario generado contra los artículos recuperados antes de mostrarlo, y medir el porcentaje de escenarios inválidos.
