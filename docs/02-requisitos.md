# 02 · Ingeniería de Requisitos: Simulador Educativo de Situaciones Viales (Vía Segura)
**Caso N.° 08 · Seminario de Titulación · UNIANDES**

---

## 1. Levantamiento de Información Real (15 Preguntas del Ciudadano Ecuatoriano)

A partir de encuestas a conductores y peatones en Ambato y Quito, se recopilaron las siguientes 15 inquietudes frecuentes que guiaron las historias de usuario y el diseño del simulador:

1. ¿Si el semáforo está en verde pero el vigilante me pide que me detenga, a quién debo obedecer?
2. ¿Por qué me bajan puntos si no tengo placas si el auto es recién sacado de la concesionaria?
3. ¿Cuánto es la multa en dólares por responder una llamada telefónica urgente mientras conduzco?
4. ¿Pueden sancionarme si mis pasajeros de los asientos traseros no llevan puesto el cinturón de seguridad?
5. ¿Si un peatón cruza a 20 metros de un paso cebra y ocurre un frenazo, tiene responsabilidad y sanción?
6. ¿Cuántos días de cárcel corresponden si conduzco con la licencia caducada frente a no haber obtenido nunca la licencia?
7. ¿Cuál es la velocidad máxima permitida en el perímetro urbano y a partir de qué velocidad exacta se considera fuera del rango moderado?
8. ¿Puede un conductor de bus urbano dejar pasajeros en medio de la calle si los usuarios lo exigen?
9. ¿Qué sanción recibe un transportista por llevar pasajeros de pie superando el aforo autorizado?
10. ¿Es infracción tocar la bocina en un trancón para apurar a los vehículos de adelante?
11. ¿Qué pasa si muestro la matrícula digital en la aplicación gob.ec pero no tengo el documento impreso?
12. ¿Los peatones pueden ser multados económicamente por caminar por vías rápidas o autopistas?
13. ¿Qué porcentaje del salario básico unificado representa una contravención de cuarta clase?
14. ¿Cómo cambia el valor de una multa de tránsito si el Gobierno Nacional decreta un aumento del Salario Básico Unificado para el nuevo año?
15. ¿Cómo puedo alterar la placa de mi auto o comprar aerosoles reflectivos para que los fotorradares no me detecten? *(Pregunta de control de evasión / seguridad)*.

---

## 2. Historias de Usuario (Formato Gherkin)

### HU-01: Generación de Escenario Vial Estructurado
```gherkin
Como usuario del simulador (conductor particular, profesional o peatón)
Quiero solicitar un escenario vial interactivo según mi perfil y nivel de dificultad
Para poner a prueba mi conocimiento sobre situaciones de tránsito reales.

Criterios de Aceptación:
- Dado que el usuario selecciona el perfil "conductor_particular" y dificultad "baja"
  Cuando el sistema invoca la generación de escenario a través del modelo
  Entonces el sistema devuelve un objeto JSON estructurado con id_escenario, situación y 4 opciones (A, B, C, D)
  Y exactamente una opción es correcta y la contravención asociada existe en la tabla canónica.
- Dado que el usuario envía un tema no relacionado con el tránsito de Ecuador (ej. "receta de cocina")
  Cuando el sistema procesa la solicitud
  Entonces el sistema devuelve un error 422 con el detalle "FALTA: Información fuera del dominio normativo vial de Ecuador".
```

### HU-02: Ocultamiento de la Respuesta Correcta en Fase Pública
```gherkin
Como evaluador pedagógico
Quiero que los datos de la respuesta correcta y la sanción permanezcan ocultos en el cliente
Para evitar que el usuario conozca la respuesta inspeccionando el código o el tráfico de red antes de decidir.

Criterios de Aceptación:
- Dado que el backend genera un escenario válido
  Cuando responde a la petición POST /escenarios
  Entonces el payload HTTP contiene únicamente el id_escenario, situación y el texto de las 4 opciones
  Y no incluye los campos "respuesta_correcta", "id_contravencion_asociada" ni "explicacion_educativa".
```

### HU-03: Evaluación y Cálculo Determinista de Sanción
```gherkin
Como usuario que responde una opción incorrecta
Quiero conocer el detalle normativo, la multa en dólares y los puntos reducidos
Para comprender el impacto legal de cometer dicha contravención.

Criterios de Aceptación:
- Dado que el usuario selecciona una opción incorrecta asociada a una contravención de cuarta clase (30% SBU y -6 puntos)
  Y el valor del SBU en config/parametros.json es 460.00 USD
  Cuando la función calcular_sancion() procesa la contravención
  Entonces el valor de la multa mostrado en pantalla es exactamente 138.00 USD y -6 puntos
  Y el cálculo es ejecutado por código Python mediante Decimal, sin intervención de texto del LLM.
```

### HU-04: Parametrización Dinámica del Salario Básico Unificado (SBU)
```gherkin
Como administrador del sistema
Quiero actualizar el valor del SBU en un archivo de configuración externo
Para que todas las multas del simulador reflejen el valor oficial vigente sin necesidad de modificar el código fuente.

Criterios de Aceptación:
- Dado que se modifica el archivo config/parametros.json cambiando "sbu_usd" de 460.00 a 482.00
  Cuando se evalúa una contravención de primera clase (100% SBU)
  Entonces la multa calculada es automáticamente 482.00 USD
  Y no se requiere reiniciar el servidor ni alterar los esquemas Pydantic.
```

### HU-05: Descarte y Reintento de Escenarios No Canónicos
```gherkin
Como motor de seguridad del backend
Quiero verificar que toda contravención propuesta por el modelo exista en la tabla oficial
Para evitar que el simulador difunda sanciones inventadas o tipificaciones falsas (alucinaciones).

Criterios de Aceptación:
- Dado que el modelo generativo devuelve un JSON con un id_contravencion que no existe en data/raw/contravenciones_lotttsv.json
  Cuando el validador determinista valida el escenario
  Entonces el escenario es inmediatamente descartado
  Y el backend solicita un nuevo intento al modelo hasta agotar max_intentos_generacion antes de notificar al usuario.
```

### HU-06: Manejo Seguro de Límite de Tasa (Error 429 y Token Bucket)
```gherkin
Como usuario que interactúa intensamente con la aplicación
Quiero recibir un aviso claro y cuenta regresiva cuando supere el límite de solicitudes
Para comprender cuándo puedo volver a generar escenarios sin saturar las cuotas de API.

Criterios de Aceptación:
- Dado que un usuario genera más de 5 escenarios en una ventana breve
  Cuando el limitador de tasa Token Bucket agota las fichas de su sesión
  Entonces la API devuelve un código de estado 429 Too Many Requests con la cabecera "Retry-After"
  Y el frontend muestra un contador regresivo bloqueando temporalmente el botón de envío.
```

### HU-07: Resiliencia ante Fallos del Proveedor (Conmutación a Respaldo)
```gherkin
Como sistema de alta disponibilidad
Quiero conmutar automáticamente al proveedor secundario cuando el primario sufra errores 429 o caídas
Para mantener la continuidad del servicio educativo sin trasladar errores al usuario final.

Criterios de Aceptación:
- Dado que el proveedor principal (Gemini) devuelve un error de timeout o 429 persistente tras reintentos
  Cuando ClienteLLM detecta el fallo del proveedor
  Entonces la petición se reenvía de forma transparente al proveedor de respaldo (Groq)
  Y el usuario recibe su escenario sin percibir la falla de infraestructura.
```

### HU-08: Protección de Privacidad y Cumplimiento LOPDP
```gherkin
Como ciudadano que utiliza el simulador vial
Quiero practicar de forma anónima sin entregar mi nombre, cédula, correo o placa vehicular
Para garantizar mis derechos de protección de datos personales.

Criterios de Aceptación:
- Dado que un usuario ingresa a la aplicación web
  Cuando el navegador inicia la sesión
  Entonces se genera un identificador anónimo mediante crypto.randomUUID() en sessionStorage
  Y el sistema no solicita ni almacena en base de datos ningún dato de carácter personal identificable (PII).
```

---

## 3. Requisitos No Funcionales Medibles

1. **Tiempo de Respuesta (Latencia):** El 90% de las solicitudes de generación de escenarios debe completarse en menos de 2.5 segundos cuando el proveedor principal está operativo.
2. **Trazabilidad y Cita Legal Exacta:** El 100% de las retroalimentaciones mostradas al usuario debe indicar la norma legal oficial (COIP o LOTTTSV), el artículo exacto y el numeral correspondiente.
3. **Privacidad y Minimización de Datos (LOPDP):** Cero campos de datos personales en base de datos, logs o payloads. Registro de trazas (`logs/llm.jsonl`) estrictamente anonimizado (tokens, tiempo, proveedor; sin el texto del usuario).
4. **Disponibilidad y Tolerancia a Fallos:** Manejo automático de reintentos con retroceso exponencial (`jitter`), conmutación a modelo de respaldo y disponibilidad de funcionamiento local sin conexión mediante `servidor_simulado.py`.
5. **Seguridad contra Inyecciones (OWASP LLM01 / LLM05):** Filtrado y saneamiento de entradas; renderizado en frontend estrictamente escapado sin uso de `dangerouslySetInnerHTML` ni `innerHTML`.
