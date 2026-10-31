# Evidencia Técnica · Semana 3: RAG, Agente y Calidad
**Simulador Educativo de Situaciones Viales (Vía Segura) · Caso N.° 08**  
**Fecha de Revisión 3:** Viernes 30 de octubre de 2026

---

## 1. Entregables Cumplidos de la Semana 3

- [x] **Ingesta Reproducible (`scripts/ingest.py`):** Fragmentación semántica por artículo sobre el COIP (Capítulo de Tránsito) y la LOTTTSV con su Reglamento. 641 artículos indexados y 0 fragmentos huérfanos.
- [x] **Base Vectorial ChromaDB Persistente y Embeddings E5 Reales:** Colección persistente `normativa` en `chroma_db/chroma.sqlite3` generada con `SentenceTransformer("intfloat/multilingual-e5-small")` (384 dimensiones) y distancia coseno.
- [x] **Pre-Filtrado Normativo por Metadatos:** Recuperación con `where={"vigente": True}`, excluyendo automáticamente normas y contravenciones derogadas de la versión de 2011.
- [x] **Cita Textual Verificada y Obligatoria:** Cada respuesta fundamentada cita el artículo y la norma exacta recuperada, disponible en el backend y visible en la interfaz React.
- [x] **Regla de Silencio y Umbral de Distancia Coseno:** Umbral de corte fijado en $0.45$ y clasificación temática de alcance (trámites administrativos ante la ANT vs. materias ajenas al tránsito), sin números de artículos en el tesauro ni patrones ad-hoc de preguntas de prueba.
- [x] **Agente con Tool Calling (`tool_calls`), Esquemas Pydantic y Rol `tool`:**
  - Esquemas Pydantic estrictos (`extra="forbid"`) por cada herramienta y definición `ESQUEMAS_HERRAMIENTAS_OPENAI`.
  - Registro central (`REGISTRO_HERRAMIENTAS`) y despachador (`despachar_herramienta`).
  - Ciclo completo Modelo → `tool_calls` → Ejecución → mensaje con `role: "tool"` → Modelo, con tope de seguridad de 6 vueltas y bloqueo de herramientas fuera de alcance (`anular_boleta_ant`, `evadir_control_vial`).
- [x] **Herramientas Deterministas del Caso 08:**
  - `buscar_normativa_rag(consulta, top_k)`
  - `identificar_contravencion_coip(consulta, articulo_recuperado)`
  - `calcular_sancion(id_contravencion)` —computado en Python con SBU 2026 ($482.00 USD) de `config/parametros.json`—
  - `verificar_cita_y_seguridad(articulo, articulos_recuperados, texto_fragmento)`
  - `registrar_progreso(usuario_id, es_correcta, multa_usd, puntos_reducidos)`
  - `ajustar_dificultad(ultimos_resultados)`
- [x] **Defensa contra Documentos Envenenados:** Interceptación y neutralización de inyecciones maliciosas en los fragmentos normativos recuperados (Revisión 3).
- [x] **Evaluación Dual (`eval/preguntas.json` y banco independiente `eval/preguntas_finales.json`):**
  - Banco de referencia (`eval/preguntas.json`): Hit@1 = **87.5%** (14/16) | Hit@5 = **100.0%** (16/16) | Silencio = **100.0%** (4/4).
  - Banco independiente (`eval/preguntas_finales.json`): Hit@1 = **87.5%** (14/16) | Hit@5 = **100.0%** (16/16) | Silencio = **100.0%** (4/4).
- [x] **Integración Continua (`.github/workflows/ci.yml`) y Suite de Pruebas:** 66 pruebas automatizadas en `pytest`, evaluación RAG y compilación de frontend en GitHub Actions.

---

## 2. Registro de Evaluación RAG (`python eval/run_eval.py`)

```text
=== Evaluacion RAG · Banco Referencia (preguntas.json) ===
[OK] Total preguntas evaluadas: 20 (16 con fuente + 4 abstencion)
[OK] Hit@1: 87.5% | Hit@5: 100.0%
[OK] Precision en Regla de Silencio (abstencion/derivacion): 100.0%

=== Evaluacion RAG · Banco Independiente Final (preguntas_finales.json) ===
[OK] Total preguntas evaluadas: 20 (16 con fuente + 4 abstencion)
[OK] Hit@1: 87.5% | Hit@5: 100.0%
[OK] Precision en Regla de Silencio (abstencion/derivacion): 100.0%
```

---

## 3. Demostración en la Interfaz Web (`http://127.0.0.1:8000`)

La aplicación web cuenta con un panel dividido en dos módulos:
1. **Módulo 1 · Simulador de Dilemas Viales:** Generación de situaciones aleatorias conforme a perfil (`conductor_particular`, `profesional`, `motociclista`, `ciclista`, `peaton`), con evaluación en código y feedback detallado.
2. **Módulo 2 · Consultor Normativo RAG y Agente Controlado:** Panel interactivo con 6 botones de demostración para la rúbrica del docente:
   - Caso Normal (Cita + Cálculo SBU)
   - Lenguaje Ciudadano (Mapeo a la norma)
   - Fuera de Alcance (Regla de Silencio)
   - Caso en Disputa (Cita y Derivación sin dictamen)
   - Herramienta Prohibida (Bloqueo de `anular_boleta_ant` en alcance controlado)
   - Documento Envenenado (Defensa activa)
