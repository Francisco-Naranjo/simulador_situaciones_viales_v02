"""NIVEL 2 · Salida en JSON validada con esquema, a través del servicio con reintentos y respaldo.

    python scripts/probar_json.py "conductor_particular" "baja" "agente de tránsito"
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from app.schemas import EscenarioVialSchema, SolicitudEscenario
from app.services.generador import construir_mensaje
from app.services.llm import ClienteLLM, ErrorLLM, cargar_prompt
from app.tools.calcular_sancion import calcular_sancion
from app.tools.contravenciones import candidatas, cargar_tabla, validar_escenario

perfil = sys.argv[1] if len(sys.argv) > 1 else "conductor_particular"
dificultad = sys.argv[2] if len(sys.argv) > 2 else "baja"
tema = " ".join(sys.argv[3:]) if len(sys.argv) > 3 else "señal de agente"

solicitud = SolicitudEscenario(perfil=perfil, nivel_dificultad=dificultad, tema=tema)
tabla = cargar_tabla()
mensaje = construir_mensaje(solicitud, candidatas(perfil, tabla))

try:
    llm = ClienteLLM()
    r = llm.generar_json(cargar_prompt("system_v3"), mensaje, EscenarioVialSchema)
except ErrorLLM as e:
    sys.exit(f"[ERROR] {e.mensaje_usuario}")

esc = r.datos
print("=== Escenario generado ===")
print(esc.model_dump_json(indent=2))

c = validar_escenario(esc, perfil, dificultad, tabla)
sancion = calcular_sancion(c)
print(f"\n[OK] Contravencion valida en tabla: {c.id_contravencion} ({c.clase})")
print(f"[OK] Sancion calculada por codigo: ${sancion.multa_usd:.2f} USD (SBU ${sancion.sbu_usd:.2f}) y -{sancion.puntos_reducidos} puntos")
print(f"[OK] Proveedor: {r.proveedor} - {r.modelo} - {r.latencia_ms} ms - tokens {r.tokens_entrada}+{r.tokens_salida} - intentos {r.intentos}")
