# Evidencia Técnica · Semana 3: RAG, Agente y Calidad
**Simulador Educativo de Situaciones Viales (Vía Segura) · Caso N.° 08**  
**Fecha de Revisión 3:** Viernes 30 de octubre de 2026

---

## 1. Entregables Cumplidos de la Semana 3

- [x] **Ingesta Reproducible (`scripts/ingest.py`):** Fragmentación semántica por artículo sobre el COIP (Capítulo de Tránsito) y la LOTTTSV con su Reglamento. 641 artículos indexados y 0 fragmentos huérfanos.
- [x] **Base Vectorial ChromaDB y Embeddings Multilingües:** Integración persistente de ChromaDB con el modelo `intfloat/multilingual-e5-small` (384 dimensiones) y cálculo de distancia coseno.
- [x] **Pre-Filtrado Normativo por Metadatos:** Recuperación con `where={"vigente": True}`, excluyendo automáticamente normas y contravenciones derogadas de la versión de 2011.
- [x] **Cita Textual Verificada y Obligatoria:** Cada respuesta fundamentada cita el artículo y la norma exacta recuperada, disponible en el backend y visible en la interfaz React.
- [x] **Regla de Silencio y Umbral de Distancia Coseno:** Umbral de corte fijado en $0.45$. Consultas ajenas (recetas, medicina) o trámites no contemplados activan abstención o derivación inmediata a la ANT sin alucinar.
- [x] **Agente de Alcance Controlado con Tope de Vueltas:** Bucle ReAct con límite estricto de 6 vueltas, lista blanca de herramientas y bloqueo pedagógico ante intentos de ejecutar acciones fuera de alcance (ej. *"borrar multa"*, *"evadir fotorradar"*).
- [x] **Herramientas Deterministas del Caso 08:**
  - `generar_escenario(nivel, perfil)`
  - `evaluar_respuesta(escenario, respuesta)`
  - `calcular_sancion(porcentaje_sbu)` —computado en Python con SBU 2026 ($482.00 USD) de `config/parametros.json`—
  - `registrar_progreso(usuario, resultado)`
  - `ajustar_dificultad(historial)`
- [x] **Defensa contra Documentos Envenenados:** Interceptación y neutralización de inyecciones maliciosas en los fragmentos normativos recuperados (Revisión 3).
- [x] **Conjunto de Evaluación (20 Casos en `eval/preguntas.json`):** Ejecutado mediante `scripts/evaluar_rag.py` y `eval/run_eval.py`, alcanzando:
  - Hit@1: **100.0%**
  - Hit@5: **100.0%**
  - Precisión en Regla de Silencio: **100.0%**
- [x] **Suite de Pruebas Automatizadas:** 63 pruebas unitarias y de integración pasando con éxito mediante `pytest`.

---

## 2. Registro de Evaluación RAG (`python eval/run_eval.py`)

```text
=== Evaluacion RAG · Caso 08: Via Segura ===
[OK] Total preguntas evaluadas: 20 (16 con fuente + 4 abstencion)
[OK] Hit@1: 100.0% | Hit@5: 100.0%
[OK] Precision en Regla de Silencio (abstencion/derivacion): 100.0%
  #01 [OK] esperado=Art. 389 -> top5=['Art. 389', 'Art. 392', 'Art. 373']
  #02 [OK] esperado=Art. 391 -> top5=['Art. 391', 'Art. 392', 'Art. 267']
  #03 [OK] esperado=Art. 385 -> top5=['Art. 385', 'Art. 392', 'Art. 244']
  #04 [OK] esperado=Art. 386 -> top5=['Art. 386', 'Art. 392', 'Art. 90']
  #05 [OK] esperado=Art. 387 -> top5=['Art. 387', 'Art. 374', 'Art. 380']
  #06 [OK] esperado=Art. 383 -> top5=['Art. 383', 'Art. 377', 'Art. 385']
  #07 [OK] esperado=Art. 392 -> top5=['Art. 392', 'Art. 390', 'Art. 392']
  #08 [OK] esperado=Art. 389 -> top5=['Art. 389', 'Art. 391', 'Art. 392']
  #09 [OK] esperado=Art. 390 -> top5=['Art. 390', 'Art. 391', 'Art. 392']
  #10 [OK] esperado=Art. 391 -> top5=['Art. 391', 'Art. 392', 'Art. 379']
  #11 [OK] esperado=Art. 392 -> top5=['Art. 392', 'Art. 392', 'Art. 390']
  #12 [OK] esperado=Art. 390 -> top5=['Art. 390', 'Art. 298', 'Art. 392']
  #13 [OK] esperado=Art. 388 -> top5=['Art. 388', 'Art. 292', 'Art. 62']
  #14 [OK] esperado=Art. 389 -> top5=['Art. 389', 'Art. 177', 'Art. 392']
  #15 [OK] esperado=Art. 373 -> top5=['Art. 373', 'Art. 392', 'Art. 392']
  #16 [OK] esperado=Art. 391 -> top5=['Art. 391', 'Art. 170', 'Art. 26']
  #17 [OK] abstencion (deriva) -> abstuvo=True
  #18 [OK] abstencion (deriva) -> abstuvo=True
  #19 [OK] abstencion (sin) -> abstuvo=True
  #20 [OK] abstencion (sin) -> abstuvo=True
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
   - Herramienta Prohibida (Bloqueo de `anular_boleta` en alcance controlado)
   - Documento Envenenado (Defensa activa)
