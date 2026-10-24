# Evidencia Técnica · Semana 2: MVP e Integración con IA Generativa
**Simulador Educativo de Situaciones Viales (Vía Segura) · Caso N.° 08**  
**Fecha de Revisión 2:** Viernes 23 de octubre de 2026

---

## 1. Entregables Cumplidos de la Semana 2

- [x] **Backend FastAPI con integración resiliente:** Endpoint `POST /escenarios` y `POST /evaluaciones`, más `/health`, operando con esquemas estrictos Pydantic (`extra="forbid"`).
- [x] **Módulo de Servicio Desacoplado (`app/services/llm.py`):** Encapsulamiento total de la llamada al modelo. Cambiar de proveedor (Gemini, Groq, simulado) no altera los endpoints.
- [x] **Manejo Robusto de Errores del Proveedor:** Reintentos con espera exponencial y jitter ante errores 429 (límite de tasa) y caídas, con conmutación automática al proveedor de respaldo.
- [x] **Limitador de Tasa Propio (Token Bucket):** Protección de la API devolviendo errores RFC 9457 `429 Too Many Requests` con la cabecera `Retry-After`.
- [x] **System Prompts Versionados y Comparados:** `system_v1.md`, `system_v2.md` y `system_v3.md` (R.E.C.E.T.A. ganador), con comparación técnica documentada en `docs/05-prompts.md` y datos en `eval/entradas_prompts.csv`.
- [x] **Frontend Funcional en React / Vite / TypeScript:** Implementa la máquina de estados estricta (`inactiva`, `cargando`, `completa`, `reintentar`, `error_servidor`), lectura de `Retry-After` con cuenta regresiva, mitigación XSS sin `innerHTML`, sesiones anónimas con `crypto.randomUUID()` y diseño Double-Bezel con marcador educativo.
- [x] **Suite de Pruebas Automatizadas con Doble de Prueba (Mock):** 51 pruebas con `pytest` que verifican cálculos deterministas, validación cruzada de contravenciones, manejo de 429, fallos de red y endpoints HTTP sin gastar cuota de API.
- [x] **Seguridad de Credenciales:** Verificación de que ninguna clave API reside en el código ni en el historial de Git; exclusión estricta en `.gitignore` y plantilla clara en `.env.example`.

---

## 2. Registro de Ejecución de Pruebas (`pytest -v`)

```text
============================= test session starts =============================
platform win32 -- Python 3.12.7, pytest-9.1.1
rootdir: D:\UNIANDES\Seminario\UNIDAD I\simulador-situaciones-viales
collected 51 items

tests/test_config.py::test_nombres_del_kit PASSED                        [  1%]
tests/test_config.py::test_nombres_de_la_clase_1 PASSED                  [  3%]
tests/test_config.py::test_linea_vacia_usa_el_valor_por_defecto PASSED   [  5%]
tests/test_config.py::test_numero_mal_escrito_da_mensaje_claro PASSED    [  7%]
tests/test_config.py::test_razonamiento_none_e_invalido PASSED           [  9%]
tests/test_endpoint.py::test_health PASSED                               [ 11%]
tests/test_endpoint.py::test_generar_escenario_oculta_respuesta_correcta PASSED [ 13%]
tests/test_endpoint.py::test_evaluar_respuesta_correcta_e_incorrecta PASSED [ 15%]
tests/test_endpoint.py::test_evaluacion_no_permite_reusar_escenario PASSED [ 17%]
tests/test_endpoint.py::test_fuera_de_dominio_retorna_422_rfc9457 PASSED [ 19%]
tests/test_endpoint.py::test_proveedor_caido_retorna_503_con_retry_after PASSED [ 21%]
tests/test_herramientas.py::test_hu02_cuarta_clase_30_por_ciento_de_460_es_138 PASSED [ 23%]
tests/test_herramientas.py::test_multa_exacta_con_decimal[...] PASSED   [ 37%]
tests/test_herramientas.py::test_multa_rechaza_valores_imposibles[...] PASSED [ 45%]
tests/test_herramientas.py::test_cambiar_sbu_en_configuracion_cambia_la_multa PASSED [ 47%]
tests/test_herramientas.py::test_parametros_rechaza_sbu_invalido PASSED  [ 49%]
tests/test_herramientas.py::test_tabla_real_carga_y_es_coherente PASSED  [ 50%]
tests/test_herramientas.py::test_misma_clase_misma_sancion_en_la_tabla PASSED [ 52%]
tests/test_herramientas.py::test_hu01_escenario_valido_devuelve_la_contravencion_canonica PASSED [ 54%]
tests/test_herramientas.py::test_contravencion_inexistente_se_descarta PASSED [ 56%]
tests/test_herramientas.py::test_contravencion_de_otro_perfil_se_descarta PASSED [ 58%]
tests/test_herramientas.py::test_dificultad_distinta_a_la_pedida_se_descarta PASSED [ 60%]
tests/test_herramientas.py::test_marca_falta_es_abstencion PASSED        [ 62%]
tests/test_herramientas.py::test_esquema_rechaza_escenarios_incoherentes[...] PASSED [ 72%]
tests/test_herramientas.py::test_respuesta_incorrecta_muestra_sancion_calculada PASSED [ 74%]
tests/test_herramientas.py::test_respuesta_correcta PASSED               [ 76%]
tests/test_integracion_simulado.py::test_json_por_http_con_429_real PASSED [ 78%]
tests/test_llm.py::test_json_valido PASSED                               [ 80%]
tests/test_llm.py::test_pide_el_esquema_al_proveedor PASSED              [ 82%]
tests/test_llm.py::test_json_invalido_se_corrige_una_vez PASSED          [ 84%]
tests/test_llm.py::test_json_invalido_dos_veces_va_a_revision_humana PASSED [ 86%]
tests/test_llm.py::test_429_respeta_retry_after_y_reintenta PASSED       [ 88%]
tests/test_llm.py::test_espera_exponencial_sin_retry_after PASSED        [ 90%]
tests/test_llm.py::test_respuesta_vacia_se_reintenta PASSED              [ 92%]
tests/test_llm.py::test_principal_caido_pasa_al_respaldo PASSED          [ 94%]
tests/test_llm.py::test_clave_invalida_no_se_reintenta PASSED            [ 96%]
tests/test_llm.py::test_todos_caidos_da_error_claro PASSED               [ 98%]
tests/test_llm.py::test_retry_after_muy_largo_va_directo_al_respaldo PASSED [100%]

============================= 51 passed in 6.04s ==============================
```
