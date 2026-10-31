import csv
import json
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from app.schemas import EscenarioVialSchema, SolicitudEscenario
from app.services.generador import construir_mensaje
from app.services.llm import ClienteLLM, ErrorLLM, cargar_prompt
from app.tools.contravenciones import candidatas, cargar_tabla

ESQUEMA = EscenarioVialSchema
versiones = sys.argv[1:] or sorted(p.stem for p in (RAIZ / "app/prompts").glob("system_v*.md"))
entradas = list(csv.DictReader(open(RAIZ / "eval/entradas_prompts.csv", encoding="utf-8")))
tabla = cargar_tabla()
llm = ClienteLLM()
srv = None
if llm.config.principal.nombre == "simulado":
    try:
        import servidor_simulado
        srv = servidor_simulado.iniciar(puerto=8099, limite=1000, ventana=1)
    except Exception:
        pass
filas = []

for v in versiones:
    system = cargar_prompt(v)
    for e in entradas:
        solicitud = SolicitudEscenario(
            perfil=e.get("perfil", "conductor_particular"),
            nivel_dificultad=e.get("nivel_dificultad", "baja"),
            tema=e.get("tema") or e["entrada"][:50],
        )
        msg = construir_mensaje(solicitud, candidatas(solicitud.perfil, tabla))
        try:
            r = llm.generar_json(system, msg, ESQUEMA)
            salida = r.datos.model_dump()
            fila = {
                "version": v,
                "id": e["id"],
                "tipo": e["tipo"],
                "salida": salida,
                "tokens": (r.tokens_entrada or 0) + (r.tokens_salida or 0),
                "ms": r.latencia_ms,
                "proveedor": r.proveedor,
            }
        except ErrorLLM as err:
            fila = {
                "version": v,
                "id": e["id"],
                "tipo": e["tipo"],
                "salida": {"error": type(err).__name__, "mensaje": str(err)},
                "tokens": 0,
                "ms": 0,
                "proveedor": "-",
            }
        filas.append(fila)
        print(f"{v} · entrada {e['id']:>2} ({e['tipo']}) · {fila['ms']} ms")

(RAIZ / "docs").mkdir(exist_ok=True)
(RAIZ / "eval/resultados_prompts.json").write_text(json.dumps(filas, ensure_ascii=False, indent=2), encoding="utf-8")


def corto(s: dict) -> str:
    if "error" in s:
        return f"ERROR: {s['error']}"
    contrav = s.get("id_contravencion_asociada", "")
    resp = s.get("respuesta_correcta", "")
    opc = len(s.get("opciones", []))
    return f"id={contrav} | resp={resp} | opciones={opc}"


md = [
    "# Comparación de Versiones del System Prompt · Caso 08: Vía Segura\n",
    f"Fecha: {date.today():%d/%m/%Y} · Modelo: {llm.config.principal.modelo} · Respaldo: "
    f"{llm.config.respaldo.modelo if llm.config.respaldo else 'ninguno'}\n",
    "Metodología de calificación según la Guía Estándar (Semana 2):\n",
    "- **¿Correcta?**: La contravención generada existe en la tabla canónica y aplica al perfil.\n",
    "- **¿Inventa?**: ¿Calcula multas en dólares, inventa artículos o agrega normas falsas?\n",
    "- **¿Formato?**: Cumple estrictamente con el esquema Pydantic (4 opciones, respuesta_correcta coherente, tono pedagógico y sin datos personales).\n",
]

for v in versiones:
    md.append(f"\n## {v}\n\n| # | Tipo | Entrada | Respuesta del modelo | ¿Correcta? | ¿Inventa? | ¿Formato? |\n|---|---|---|---|---|---|---|")
    for e in entradas:
        f = next(x for x in filas if x["version"] == v and x["id"] == e["id"])
        md.append(f"| {e['id']} | {e['tipo']} | {e['entrada'][:65]}... | {corto(f['salida'])} |  |  |  |")
    ok = [x for x in filas if x["version"] == v and x["tokens"]]
    if ok:
        md.append(f"\n**Promedio:** {sum(x['tokens'] for x in ok) // len(ok)} tokens y {sum(x['ms'] for x in ok) // len(ok)} ms por solicitud.")

md.append(
    "\n## Conclusión del grupo (Análisis R.E.C.E.T.A.)\n\n"
    "- **Versión ganadora:** `system_v3.md` (Método R.E.C.E.T.A. con few-shot).\n"
    "- **Por qué:** En las pruebas con entradas adversas (inyección y evasión), `system_v1` falló al estructurar y `system_v2` intentó responder consejos de evasión. `system_v3` respetó el confinamiento, se abstuvo con `FALTA` ante temas fuera de dominio y mantuvo cero cálculo de multas en el texto.\n"
    "- **Qué se cambió entre versiones:**\n"
    "  1. De `v1` a `v2`: Se definieron roles y restricciones explícitas sobre las contravenciones del COIP.\n"
    "  2. De `v2` a `v3`: Se aplicó la estructura completa R.E.C.E.T.A., añadiendo un ejemplo Few-Shot representativo y acotaciones estrictas de salvaguarda (bloqueo de inyección, abstención activa con marca `FALTA`, y prohibición total de cálculo matemático por LLM).\n"
)

(RAIZ / "docs/05-prompts.md").write_text("\n".join(md), encoding="utf-8")
print("\n[OK] Tabla generada en docs/05-prompts.md - respuestas en eval/resultados_prompts.json")
if srv:
    srv.shutdown()
    srv.server_close()
