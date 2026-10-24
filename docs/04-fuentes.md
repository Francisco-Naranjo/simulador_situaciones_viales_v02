# 04 · Inventario de Fuentes de la Base de Conocimiento
**Caso N.° 08 · Simulador Educativo de Situaciones Viales (Vía Segura) · UNIANDES**  
**Fecha de Verificación:** Octubre 2026

---

## 1. Inventario Oficial de Fuentes Normativas

La base de conocimiento de «Vía Segura» se fundamenta exclusivamente en instrumentos jurídicos y técnicos oficiales vigentes de la República del Ecuador:

| # | Documento | Origen Oficial | URL / Repositorio | Fecha de Publicación / Vigencia | Formato | Rol en el Sistema |
|---|---|---|---|---|---|---|
| **F-01** | **Código Orgánico Integral Penal (COIP)** — Capítulo Octavo: Infracciones de Tránsito, Sección Tercera: Contravenciones (Arts. 383 a 392). | Asamblea Nacional del Ecuador / Registro Oficial | [https://www.ant.gob.ec](https://www.ant.gob.ec) / [Asamblea Nacional](https://www.asambleanacional.gob.ec) | Registro Oficial Suplemento 180 de 10-feb-2014, con reformas consolidadas a 2026. | Ley Oficial / PDF y `data/raw/contravenciones_lotttsv.json` | Tipificación canónica obligatoria de contravenciones de 1.ª a 7.ª clase, porcentaje de SBU y reducción de puntos. |
| **F-02** | **Ley Orgánica de Transporte Terrestre, Tránsito y Seguridad Vial (LOTTTSV)** y su Ley Orgánica Reformatoria. | Asamblea Nacional del Ecuador | [https://www.ant.gob.ec](https://www.ant.gob.ec) | Registro Oficial Suplemento 398 de 07-ago-2008; reformas R.O. Suplemento 512 de 10-ago-2021. | Ley Oficial / PDF | Deberes y derechos de conductores, peatones y pasajeros; jerarquía de señales y títulos habilitantes. |
| **F-03** | **Reglamento General para la Aplicación de la LOTTTSV** | Presidencia de la República / ANT | [https://www.ant.gob.ec](https://www.ant.gob.ec) | Registro Oficial Suplemento 731 de 25-jun-2012 y reformas vigentes. | Decreto Ejecutivo / PDF | Normas operativas de circulación, pasos cebra, señalética manual de agentes y rangos moderados de velocidad. |
| **F-04** | **Acuerdo Ministerial del Salario Básico Unificado (SBU)** | Ministerio del Trabajo del Ecuador | [https://www.trabajo.gob.ec](https://www.trabajo.gob.ec) | Acuerdo Ministerial anual (Valor de referencia base: $460.00 USD). | Acuerdo Ministerial / JSON (`config/parametros.json`) | Parámetro dinámico para el cálculo determinista de las sanciones económicas en dólares. |
| **F-05** | **Manual de Educación Vial y Señalización de Tránsito** | Agencia Nacional de Tránsito (ANT) | [https://www.ant.gob.ec](https://www.ant.gob.ec) | Resoluciones y manuales vigentes (edición 2024–2026). | Guía Técnica / PDF | Corpus pedagógico para la redacción de opciones distractivas y explicaciones formativas. |

---

## 2. Estrategia de Estructuración y Fragmentación (Semana 1 a Semana 3)

### Fase Inicial (Semanas 1 y 2 · Tabla Canónica Estructurada)
Para el MVP y la integración con el modelo generativo, la fuente primaria opera como una **base estructurada determinista** (`data/raw/contravenciones_lotttsv.json`). Cada infracción contiene:
- `id_contravencion`: Código único inmutable (ej. `CONT-COIP-ART389-1`).
- `clase`: Clase de contravención (Primera a Séptima clase).
- `articulo` y `norma`: Cita legal precisa.
- `descripcion_infraccion`: Tipificación textual de la conducta.
- `porcentaje_sbu`: Porcentaje matemático exacto para cómputo determinista.
- `puntos_reducidos`: Puntos sancionados de la licencia de conducir.
- `perfiles_aplicables`: Lista de perfiles autorizados (`conductor_particular`, `conductor_profesional`, `peaton`).

### Fase de Inteligencia Avanzada (Semana 3 · Estrategia RAG por Artículo)
En la semana 3, para la retroalimentación ampliada y consultas complejas, se aplicará una fragmentación guiada por la estructura legal:
- **Unidad de Fragmentación (Chunk):** Por **artículo legal completo** (evitando cortes ciegos por caracteres que mutilen numerales o sanciones).
- **Metadatos obligatorios por fragmento:**
  - `documento`: Nombre de la norma (ej. `COIP`, `LOTTTSV`, `Reglamento LOTTTSV`).
  - `articulo`: Número de artículo y numeral exacto.
  - `clase`: Clasificación de la infracción si aplica.
  - `fecha_vigencia`: Fecha de la última reforma aplicable al fragmento.
  - `fuente_url`: Enlace oficial verificado para consulta ciudadana.
- **Índice Vectorial:** Almacenado en disco mediante ChromaDB con embeddings semánticos para recuperación por similitud contextual ante consultas libres.
