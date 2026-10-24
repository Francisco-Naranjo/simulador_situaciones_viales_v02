# Evidencia Técnica · Semana 1: Definición del Problema y Diseño
**Simulador Educativo de Situaciones Viales (Vía Segura) · Caso N.° 08**  
**Fecha de Revisión 1:** Viernes 16 de octubre de 2026

---

## 1. Entregables Cumplidos de la Semana 1

- [x] `docs/01-propuesta.md`: Problema real, perfiles de usuario, alcance positivo y negativo estricto, análisis de riesgos OWASP y justificación del modelo generativo.
- [x] `docs/02-requisitos.md`: 8 historias de usuario detalladas en formato Gherkin con criterios de aceptación verificables, requisitos no funcionales medibles y levantamiento de 15 preguntas reales del ciudadano.
- [x] `docs/03-arquitectura.md`: Diagrama Mermaid completo de componentes (Frontend, Backend, Limitador de tasa, Herramientas, Tabla canónica, Modelos), descripción del flujo extremo a extremo y arquitectura de seguridad.
- [x] `docs/04-fuentes.md`: Inventario catalogado de fuentes oficiales (COIP, LOTTTSV, Reglamento, Acuerdo SBU, Manual ANT) con fechas de vigencia, URLs oficiales y estrategia de fragmentación.
- [x] Repositorio Git estructurado: `.gitignore`, `.env.example`, dependencias en `requirements.txt` y esqueleto ejecutable de FastAPI con endpoint `/health` operativo.

---

## 2. Decisiones Técnicas Clave de la Semana 1

1. **Adopción del Principio «El modelo propone, el código dispone»:**  
   Se definió que el modelo generativo jamás computará multas ni puntos de licencia; toda sanción se calculará en Python a partir del SBU parametrizado en `config/parametros.json`.
2. **Modelado de tres perfiles de usuario:**  
   `conductor_particular`, `conductor_profesional` y `peaton`, cada uno con un subconjunto específico de contravenciones aplicables en la tabla canónica.
3. **Privacidad por diseño (LOPDP):**  
   Se optó por no solicitar ni persistir ningún dato personal (PII), utilizando sesiones anónimas efímeras (`X-Session-ID`).
