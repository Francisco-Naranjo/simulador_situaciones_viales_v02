# 01 · Propuesta del Proyecto: Simulador Educativo de Situaciones Viales (Vía Segura)
**Caso N.° 08 · Proceso de Titulación Complexivo · Carrera de Software · UNIANDES**  
**Fecha:** Octubre 2026  
**Semana 1 y 2**

---

## 1. Problema Real

En el Ecuador, conductores y peatones desconocen frecuentemente qué conductas constituyen contravenciones de tránsito, cuántos puntos se reducen de la licencia de conducir, qué sanción pecuniaria corresponde y qué pasos seguir ante incidentes en las vías públicas. 

La Ley Orgánica de Transporte Terrestre, Tránsito y Seguridad Vial (LOTTTSV), su Reglamento General y el Código Orgánico Integral Penal (COIP, arts. 383–392) contienen esta tipificación legal. Sin embargo, su estructura punitiva clasificada en siete clases de contravenciones y su lenguaje estrictamente jurídico resultan de muy difícil consulta y comprensión para el ciudadano común. 

La educación vial tradicional se ha sustentado en la memorización estática de reactivos y no en el análisis situacional de dilemas en contexto real (factores climáticos, presión de tiempo, desobediencia a señales, distractores tecnológicos). Esto deriva en alta siniestralidad, pérdida acumulada de puntos y multas imprevistas.

---

## 2. Usuarios Objetivo y Perfiles

El sistema modela tres perfiles diferenciados con competencias y riesgos específicos:

1. **Conductor Particular:** Ciudadanos que conducen automóviles, motocicletas o camionetas privadas. Requieren reforzar el respeto a límites de velocidad, señales del agente, fotorradares, uso del cinturón de seguridad y prohibición de dispositivos distractores (celulares).
2. **Conductor Profesional:** Choferes de buses urbanos/interprovinciales, taxis y transporte de carga pesada. Están sujetos a normativas de paradas autorizadas, aforo de pasajeros, permisos de operación y transporte de materiales peligrosos.
3. **Peatón:** Ciudadanos que se desplazan a pie en vías urbanas y carreteras. Requieren interiorizar el uso obligatorio de pasos cebra, puentes peatonales y la prohibición de transitar por autopistas o calzadas de alta velocidad.

---

## 3. Alcance del Sistema (Positivo y Negativo)

### Lo que el sistema HACE (Alcance Positivo)
- Genera dilemas viales dinámicos, inmersivos y pedagógicos contextualizados en vías y situaciones cotidianas de Ecuador.
- Asocia cada situación a una contravención real tipificada en la tabla canónica del COIP/LOTTTSV.
- Presenta al usuario cuatro opciones de decisión donde solo una cumple la norma.
- Evalúa de forma determinista la respuesta del usuario en el backend.
- Computa matemáticamente el valor de la multa en dólares mediante el Salario Básico Unificado (SBU) vigente configurado en `config/parametros.json` y la reducción de puntos de licencia.
- Entrega retroalimentación formativa inmediata con la cita exacta del artículo legal correspondiente.
- Protege la privacidad del usuario operando mediante sesiones anónimas efímeras (`X-Session-ID`), sin requerir ningún dato personal identificable (PII), en estricto cumplimiento de la Ley Orgánica de Protección de Datos Personales (LOPDP).

### Lo que el sistema NUNCA HARÁ (Alcance Negativo Obligatorio)
- **Nunca brindará asesoría legal ni patrocinio judicial:** El simulador es exclusivamente una herramienta de aprendizaje y entrenamiento pedagógico.
- **Nunca enseñará ni sugerirá métodos de evasión:** Ante consultas sobre cómo burlar radares, ocultar placas, evadir controles policiales o falsificar documentos, el sistema se negará rotundamente o se abstendrá activamente.
- **Nunca dejará cálculos matemáticos al modelo generativo:** El LLM jamás computa valores en dólares ni deducción de puntos; toda sanción se calcula mediante funciones deterministas en Python.
- **Nunca procesará temas ajenos a la seguridad vial de Ecuador:** Consultas de tributación, salud, laboral o recetas de cocina son rechazadas con la respuesta formal de abstención `FALTA`.

---

## 4. Matriz de Riesgos Identificados

| Riesgo | Impacto | Probabilidad | Estrategia de Mitigación |
|---|---|---|---|
| **Alucinación de artículos o multas (OWASP LLM09)** | Crítico | Media | Esquema Pydantic estricto (`extra="forbid"`), validación determinista cruzada contra la tabla canónica JSON y prohibición absoluta de cálculo en el prompt. |
| **Inyección de Prompt directa o indirecta (OWASP LLM01)** | Alto | Media | Delimitación estricta de entradas del usuario bajo etiquetas XML (`<solicitud>...</solicitud>`), instrucción explícita de confinamiento en el prompt y pruebas de penetración en `eval/`. |
| **Consumo excesivo y Denegación de Servicio (OWASP LLM10)** | Alto | Alta | Limitador de tasa (Token Bucket) en memoria por sesión/IP, que devuelve un error RFC 9457 `429 Too Many Requests` con cabecera `Retry-After`. |
| **Fuga de credenciales o claves API (OWASP LLM07)** | Crítico | Baja | Las claves API residen únicamente en `.env`, excluido rigurosamente del repositorio mediante `.gitignore`. |
| **Agotamiento de cuota de API (Error 429 del proveedor)** | Medio | Media | Implementación de reintentos con espera exponencial y jitter aleatorio, más conmutación automática a proveedor de respaldo (Groq). |

---

## 5. Justificación del Modelo Generativo Elegido

- **Modelo Principal:** **Google Gemini (capa gratuita: `gemini-3.8-flash`)**
  - **Justificación Técnica:** Excelente capacidad de seguimiento de esquemas JSON estructurados (`response_format`), baja latencia de respuesta (inferior a 1.2 segundos), amplia ventana de contexto para el prompt estructurado y coste cero para estudiantes de titulación.
  - **Control de Inferencia:** En lugar de temperatura libre, se calibra mediante `LLM_RAZONAMIENTO=low` para garantizar respuestas deterministas y ceñidas al corpus legal.
- **Modelo de Respaldo:** **Groq (`openai/gpt-oss-20b` / `llama-3.3-70b-versatile`)**
  - **Justificación Técnica:** Servidor de inferencia ultrarrápido compatible con la API de OpenAI Chat Completions, con 30 peticiones/minuto gratuitas, permitiendo tolerar caídas o límites de tasa de Gemini sin afectar la sesión del usuario.
