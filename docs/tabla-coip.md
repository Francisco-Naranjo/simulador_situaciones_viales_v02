# 07 · Tabla de contravenciones de tránsito (COIP, arts. 386–392)

Archivo: `data/tabla_contravenciones.csv` (90 filas) y `data/raw/contravenciones_lotttsv.json`. Se regeneran y verifican contra `data/raw/AMT-COIP-CAPITULO-TRANSITO.pdf` con `python scripts/construir_tabla.py`.

## Resumen por clase
| Clase | Artículo | Multa (% SBU) | Puntos según el texto | Puntos aplicables hoy* | Filas |
|---|---|---|---|---|---|
| 1ª | 386 | 100 % (200 % en el 2.º inciso) | 10 | 10 (0 en el numeral 1) | 6 |
| 2ª | 387 | 50 % | 9 | 9 | 5 |
| 3ª | 388 | 40 % | 7,5 | 0 | 9 |
| 4ª | 389 | 30 % | 6 | 0 | 12 |
| 5ª | 390 | 15 % | 4,5 | 0 | 22 |
| 6ª | 391 | 10 % | 3 | 0 | 21 |
| 7ª | 392 | 5 % | 1,5 | 0 | 15 |

\* Según la reforma publicada en el Registro Oficial Suplemento 512 (10-ago-2021), que suprimió la reducción de puntos de la 3.ª a la 7.ª clase.

## Columnas
- `puntos_texto_coip`: lo que dice el artículo. `puntos_aplicables`: lo que el simulador debe mostrar. Se separan para poder citar el artículo sin afirmar una reducción que ya no se aplica.
- `pena_adicional`: prisión, retención del vehículo, retiro de licencia, etc.
- `perfil_aplica`: filtro para generar escenarios por perfil (`particular`, `profesional`, `motociclista`, `ciclista`, `peaton`).
- `solo_multa_ciclista_peaton`: los arts. 387–392 indican que a ciclistas y peatones se les aplica solo la multa.
- Las descripciones están **resumidas con palabras propias**; el texto íntegro de cada numeral va en la base RAG (`data/raw/`).

## Cómo se calcula la multa
`multa_usd = porcentaje_sbu / 100 × SBU` con el SBU de `config/parametros.json` (482 USD en 2026):
100 % = 482,00 · 50 % = 241,00 · 40 % = 192,80 · 30 % = 144,60 · 15 % = 72,30 · 10 % = 48,20 · 5 % = 24,10.

## Estado de verificación (importante)
- Fuente contrastada: texto íntegro de los artículos 371–392 en `data/raw/AMT-COIP-CAPITULO-TRANSITO.pdf` y reforma del Registro Oficial Suplemento 512 (10-ago-2021).
- Todas las 90 filas se encuentran en `estado_verificacion = verificado` tras contraste automatizado en `scripts/construir_tabla.py`.
- Alcance: contravenciones de tránsito (arts. 386–392) en la tabla estructurada, y capítulo completo de infracciones de tránsito (arts. 371–392, incluyendo embriaguez art. 385) indexado por artículo en la base RAG (`data/processed/indice_rag.json`).
