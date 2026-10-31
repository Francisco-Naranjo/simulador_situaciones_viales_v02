# Vía Segura · Simulador Educativo de Situaciones Viales y Contravenciones

**Seminario de Titulación Complexivo: Ingeniería de Software con IA Generativa**  
**Carrera de Software · Facultad de Sistemas Mercantiles · UNIANDES**  
**Caso N.° 08 · Grupo 8 · Semanas 1, 2 y 3 (RAG)**

---

## 1. Identificación del Proyecto
- **Nombre del Producto:** Vía Segura — Simulador Educativo de Dilemas Viales y Contravenciones
- **Caso Asignado:** Caso 08 (Simulador educativo con RAG y retroalimentación normativa COIP/LOTTTSV)
- **Familia de Producto:** Planificadores y Simuladores Interactivos
- **Equipo de Desarrollo:** Grupo 8 · Carrera de Software, UNIANDES

---

## 2. Problema que Resuelve y Usuarios
Los conductores y peatones en Ecuador desconocen con frecuencia qué conductas configuran contravenciones de tránsito, cuántos puntos se reducen de la licencia y el monto exacto de las multas según el COIP. La educación vial tradicional memorística no prepara para dilemas cotidianos. 

**Vía Segura** presenta dilemas viales situacionales generados por IA a partir de una tabla canónica oficial, evalúa las decisiones del usuario de forma 100% determinista y entrega retroalimentación formativa con el cálculo exacto de la multa y la cita del artículo legal correspondiente.

---

## 3. Estado del Proyecto y Despliegue
- **Fase Actual:** Semanas 1, 2 y 3 (MVP, integración con IA Generativa y sistema RAG normativo completados al 100%)
- **Estado de Pruebas:** 63 pruebas automatizadas pasando con éxito (`pytest`) y evaluación RAG con `Hit@1 = 100%` y `Hit@5 = 100%` (`eval/preguntas.json`)
- **URL Local del Backend + Frontend:** `http://127.0.0.1:8000/` (FastAPI sirve el build compilado de React)
- **Documentación Interactiva Swagger / OpenAPI:** `http://127.0.0.1:8000/docs`
- **Endpoints de la Semana 3:** `POST /chat` (Asistente RAG con agente de alcance controlado) y `GET /rag/buscar` (Buscador semántico en ChromaDB)
- **Despliegue en la Nube:** Programado para la Semana 4 (Render / Railway)

---

## 4. Arquitectura y Flujo de una Consulta
La arquitectura sigue el principio fundamental: **«El modelo propone, el código dispone»**.

```
[Usuario / Frontend React]
       │
       ▼ (1) POST /escenarios
[FastAPI / Limitador Token Bucket (429)]
       │
       ▼ (2) Prompt R.E.C.E.T.A. + Contravenciones Canónicas
[ClienteLLM: Gemini-3.8-flash (Respaldo: Groq)]
       │
       ▼ (3) Salida JSON Pydantic (extra="forbid")
[Validador Cruzado Determinista contra data/raw/contravenciones_lotttsv.json]
       │
       ▼ (4) Retorna EscenarioPublico (Respuesta correcta OCULTA)
[Usuario selecciona opción A, B, C o D]
       │
       ▼ (5) POST /evaluaciones
[Evaluador y Calculador Python con Decimal y SBU de config/parametros.json]
       │
       ▼ (6) Retroalimentación con Multa en USD y Cita al Artículo del COIP
```

---

## 5. Base de Conocimiento y Fuentes Oficiales
1. **Código Orgánico Integral Penal (COIP):** Arts. 383 a 392 (Contravenciones de 1.ª a 7.ª clase). Registro Oficial Suplemento 180, con reformas consolidadas vigentes a 2026.
2. **Ley Orgánica de Transporte Terrestre, Tránsito y Seguridad Vial (LOTTTSV):** Registro Oficial Suplemento 398 de 07-ago-2008 y Ley Reformatoria (R.O. Suplemento 512 de 10-ago-2021).
3. **Reglamento General a la LOTTTSV:** Registro Oficial Suplemento 731 de 25-jun-2012.
4. **Tabla Canónica y Documentación COIP:** `data/raw/contravenciones_lotttsv.json` (90 contravenciones verificadas del COIP Arts. 386–392), documentada en `docs/tabla-coip.md` y `docs/tabla_contravenciones.csv`, es la única fuente de verdad estructurada para sanciones.
5. **Vigencia y Actualización:** El Salario Básico Unificado (SBU 2026: $482.00 USD) se actualiza de forma externa en `config/parametros.json` sin alterar el código ni el prompt.

---

## 6. Herramientas Deterministas del Agente y RAG (Semana 3)
Toda decisión crítica, cálculo financiero, validación jurídica y búsqueda normativa se ejecuta en código determinista probado, **NUNCA por el LLM**:
- `validar_escenario(esc, perfil, dificultad)`: Verifica que la contravención generada por el LLM exista en la tabla oficial y aplique al perfil. Si no coincide, descarta el escenario y solicita regeneración.
- `calcular_sancion(contravencion)`: Lee el SBU de `config/parametros.json` ($482.00 USD) y calcula la multa en USD con precisión `Decimal` (`ROUND_HALF_UP`) y la reducción de puntos de licencia según el COIP y la reforma del RO 512.
- `evaluar_respuesta(esc, contravencion, respuesta)`: Compara la opción elegida por el usuario contra la respuesta correcta verificada y genera el resultado pedagógico.
- `consultar_normativa(pregunta)` / `ServicioRAG`: Busca en **ChromaDB** (`intfloat/multilingual-e5-small`) con pre-filtro `where={"vigente": True}`, umbral de distancia coseno ($d \le 0.45$) y verificación obligatoria de cita textual.
- `agente_controlado`: Agente en `app/services/agente.py` con tope estricto de 6 vueltas, lista blanca de herramientas y bloqueo pedagógico de acciones fuera de alcance (ej. *"borrar multa"*).

---

## 7. Instalación y Puesta en Marcha Local

### Prerrequisitos
- Python 3.11 o 3.12
- Node.js 18+ y npm (opcional, ya que el build de React se incluye compilado)

### Paso 1: Clonar y configurar entorno virtual
```bash
git clone <url-del-repositorio>
cd simulador-situaciones-viales

# Crear y activar entorno virtual
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate
```

### Paso 2: Instalar dependencias
```bash
pip install -r requirements.txt
```

### Paso 3: Configurar variables de entorno
```bash
# Copiar plantilla
cp .env.example .env     # Windows: copy .env.example .env
```
Edite `.env` y configure sus claves de API gratuitas:
- **Gemini:** [Google AI Studio](https://aistudio.google.com/apikey)
- **Groq:** [Groq Console](https://console.groq.com/keys)
*(O use `LLM_PRINCIPAL=simulado` para operar en modo offline sin conexión).*

### Paso 4: Ejecutar la aplicación
```bash
uvicorn app.main:app --reload
```
Abra su navegador en:
- **Aplicación Web Interactiva:** `http://127.0.0.1:8000/`
- **Documentación Swagger API:** `http://127.0.0.1:8000/docs`

---

## 8. Variables de Entorno Requeridas (`.env.example`)
Las credenciales residen estrictamente en variables de entorno (OWASP LLM07); ninguna clave toca el repositorio:

| Variable | Propósito | Valor por Defecto |
|---|---|---|
| `LLM_PRINCIPAL` | Proveedor primario de IA (`gemini`, `groq`, `simulado`) | `gemini` |
| `LLM_RESPALDO` | Proveedor secundario de contingencia ante caídas o 429 | `groq` |
| `GEMINI_API_KEY` | Clave API gratuita de Google Gemini | *(Secreta en .env)* |
| `GEMINI_MODEL` | Identificador del modelo Gemini | `gemini-3.8-flash` |
| `GROQ_API_KEY` | Clave API gratuita de Groq | *(Secreta en .env)* |
| `GROQ_MODEL` | Identificador del modelo en Groq | `openai/gpt-oss-20b` |
| `LLM_TIMEOUT_S` | Tiempo límite de espera en segundos por llamada | `30` |
| `LLM_MAX_TOKENS` | Longitud máxima de respuesta en tokens | `2048` |
| `LLM_REINTENTOS` | Número de reintentos con espera exponencial ante 429 | `3` |
| `LLM_RAZONAMIENTO` | Nivel de razonamiento del modelo (`low`, `medium`, `high`) | `low` |

---

## 9. Ejecución de Pruebas Automatizadas
La suite de pruebas automatizadas se ejecuta sin consumir cuota de API mediante dobles de prueba (mocks):

```bash
# Ejecutar todas las 63 pruebas unitarias e integrales (incluye RAG y Agente)
python -m pytest -v

# Evaluación del sistema RAG con métricas de acierto Hit@1, Hit@5 y Regla de Silencio
python scripts/evaluar_rag.py

# Demostración del manejo de límites de tasa 429 en vivo
python scripts/demo_429.py
```

---

## 10. Resultados de Evaluación de Prompts (Semana 2)
Comparación de las tres versiones del prompt con las 10 entradas de `eval/entradas_prompts.csv` (detallada en `docs/05-prompts.md`):

| Criterio Evaluado | `system_v1.md` (Zero-Shot) | `system_v2.md` (Reglas) | `system_v3.md` (R.E.C.E.T.A.) |
|---|---|---|---|
| **Estructura y Esquema Pydantic** | 60% (fallos de clave) | 90% | **100% válido** |
| **Cero Alucinación de Multas/Puntos** | 40% (calculó en texto) | 80% | **100% (cero cálculo por LLM)** |
| **Bloqueo de Inyección y Evasión** | 0% (obedeció jailbreak) | 50% | **100% bloqueado** |
| **Abstención Fuera de Dominio** | 0% (inventó datos) | 50% | **100% abstención con `FALTA`** |
| **Versión Ganadora** | Descartada | Descartada | **Seleccionada para producción** |

---

## 11. Limitaciones Conocidas y Trabajo Futuro
- **Semana 2 (Implementado):** Generación de dilemas viales con validación cruzada contra las 90 contravenciones estructuradas del COIP (`data/raw/contravenciones_lotttsv.json` y `docs/tabla-coip.md`).
- **Semana 3 (Implementado):** Base vectorial **ChromaDB** persistente (`intfloat/multilingual-e5-small`) con pre-filtrado de metadatos (`vigente=True`), corte por artículo legal (641 fragmentos indexados, 0 huérfanos), cita verificada obligatoria, umbral de distancia coseno, detección de documentos envenenados, agente ReAct acotado (tope 6 vueltas) y pipeline de automatización en 4 estaciones en el endpoint `POST /chat` y panel React.
- **Límite de Tasa en Memoria:** El limitador Token Bucket actual opera en memoria local de la instancia; para despliegues distribuidos multi-instancia en la Semana 4 se recomienda almacenamiento compartido tipo Redis.

---

## 12. Consideraciones Éticas y Protección de Datos Personales
- **Cumplimiento LOPDP (Ecuador):** El sistema opera bajo el principio de minimización de datos. No se solicita, procesa ni almacena ningún dato de carácter personal identificable (PII). Las sesiones se identifican mediante identificadores anónimos generados en el navegador (`crypto.randomUUID()`).
- **Límites Éticos:** El sistema no asesora en juicios ni sugiere atenuantes para evadir la justicia. Ante cualquier consulta de evasión de fotorradares, el sistema rechaza la solicitud y redirige a la conducción responsable.
- **Aviso Educativo Obligatorio:** Se muestra al usuario la advertencia permanente de que el simulador es un recurso pedagógico que no reemplaza a las fuentes normativas oficiales de la ANT.

---

## 13. Declaración de Uso de IA y Aportes del Equipo

### Declaración de Uso de IA Generativa en el Desarrollo
- **Herramientas utilizadas:** Claude Opus 5.5, Gemini 3.8 Flash y Antigravity AI Assistant.
- **Usos:** Generación de borradores de esquemas Pydantic, construcción de plantillas de prueba en pytest, redacción inicial de documentación técnica y diseño de interfaces con Tailwind CSS.
- **Verificación:** Todo el código generado fue revisado línea por línea, contrastado con el Código Orgánico Integral Penal vigente y validado contra una suite automatizada de 63 pruebas que pasan al 100% y evaluación RAG con 20 casos de prueba. Las fuentes normativas fueron verificadas directamente en los repositorios oficiales de la ANT y Registro Oficial.

### Aporte por Integrante del Equipo
- **Fausto Cando (Arquitectura y Backend):** Configuración del servicio FastAPI, esquemas Pydantic estrictos, cliente LLM desacoplado, limitador Token Bucket y pruebas con mocks.
- **Isidoro Guaman (Base Canónica y Prompts):** Extracción y estructuración de las contravenciones del COIP, diseño y comparativa experimental de los prompts v1, v2 y v3 bajo el método R.E.C.E.T.A.
- **Luis Naranjo (Frontend y Documentación):** Desarrollo de la interfaz de usuario en React/TypeScript con máquina de estados estricta, manejo de cuenta regresiva 429, redacción de `docs/01-05.md` y evidencias semanales.
