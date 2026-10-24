"""NIVEL 1 · Su primera llamada real al modelo (sin protecciones, solo para ver cómo funciona).

    python scripts/primera_llamada.py            → usa Gemini
    python scripts/primera_llamada.py groq       → usa Groq (mismo código, otro proveedor)
    python scripts/primera_llamada.py simulado   → plan B sin internet
                                                   (antes, en otra terminal: python scripts/servidor_simulado.py)
"""
import os
import sys
import time

from dotenv import load_dotenv
from openai import OpenAI, APIConnectionError, APIStatusError

load_dotenv()  # 1) lee las claves del archivo .env (nunca las escriba aquí)

# Lo ÚNICO que cambia entre proveedores son estos tres valores.
PROVEEDORES = {
    "gemini":   {"clave": "GEMINI_API_KEY", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
                 "modelo": os.getenv("GEMINI_MODEL") or os.getenv("LLM_MODEL") or "gemini-3.8-flash"},
    "groq":     {"clave": "GROQ_API_KEY",   "base_url": "https://api.groq.com/openai/v1",
                 "modelo": os.getenv("GROQ_MODEL") or os.getenv("LLM_FALLBACK_MODEL") or "openai/gpt-oss-20b"},
    "simulado": {"clave": None,             "base_url": "http://127.0.0.1:8099/v1", "modelo": "simulado-1"},
}

nombre = (sys.argv[1] if len(sys.argv) > 1 else "gemini").lower()
if nombre not in PROVEEDORES:
    sys.exit(f"Proveedor desconocido: «{nombre}». Use: gemini, groq o simulado.")
p = PROVEEDORES[nombre]
clave = os.getenv(p["clave"], "").strip() if p["clave"] else "no-se-necesita"
if not clave:
    sys.exit(f"Falta {p['clave']} en el archivo .env. Ábralo y pegue su clave después del signo =, sin espacios ni comillas.")

# 2) el cliente: a quién le hablamos y con qué clave
cliente = OpenAI(api_key=clave, base_url=p["base_url"], timeout=30)

print(f"Proveedor: {nombre} · modelo: {p['modelo']}")
inicio = time.perf_counter()
try:
    # 3) la llamada: el mensaje de sistema (las reglas) y el del usuario (la pregunta)
    respuesta = cliente.chat.completions.create(
        model=p["modelo"],
        messages=[
            {"role": "system", "content": "Respondes en español, en una sola oración."},
            {"role": "user", "content": "¿Qué es un error 429 en una API?"},
        ],
    )
except APIStatusError as e:
    ayuda = {400: "la clave o la solicitud no son válidas: copie la clave de nuevo",
             401: "la clave no es válida: copie la clave de nuevo",
             403: "la clave no tiene permiso para este modelo",
             404: "el nombre del modelo está mal escrito en el .env",
             429: "se acabó la cuota por ahora (límite por minuto o por día): espere o use el otro proveedor"}
    sys.exit(f"Error {e.status_code}: {ayuda.get(e.status_code, 'el proveedor rechazó la llamada')}.")
except APIConnectionError:
    extra = " ¿Arrancó el servidor simulado en otra terminal?" if nombre == "simulado" else " Revise el internet."
    sys.exit("No se pudo conectar con el proveedor." + extra)
segundos = time.perf_counter() - inicio

u = respuesta.usage
print("Respuesta:", respuesta.choices[0].message.content)
print("Tokens de entrada:", u.prompt_tokens, "· de salida:", u.completion_tokens)
detalle = getattr(u, "completion_tokens_details", None)
razonamiento = getattr(detalle, "reasoning_tokens", None) if detalle else None
if razonamiento:
    print(f"  (de esos {u.completion_tokens}, {razonamiento} fueron de razonamiento: el modelo «pensó» antes de escribir)")
print(f"Tiempo: {segundos:.1f} s")
