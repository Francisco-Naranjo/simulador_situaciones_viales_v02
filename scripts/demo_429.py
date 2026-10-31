import argparse
import dataclasses
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import openai

from app.config import CATALOGO, Config, _proveedor
from app.services.llm import ClienteLLM, ErrorLLM

for _h in list(logging.getLogger("llm").handlers):
    if not isinstance(_h, logging.FileHandler):
        logging.getLogger("llm").removeHandler(_h)

ap = argparse.ArgumentParser()
ap.add_argument("--proveedor", default="simulado", choices=list(CATALOGO))
ap.add_argument("--n", type=int, default=8, help="solicitudes simultáneas")
a = ap.parse_args()

if a.proveedor == "simulado":
    import servidor_simulado
    try:
        servidor_simulado.iniciar(limite=5, ventana=10)
    except OSError:
        sys.exit(
            "El servidor simulado ya está abierto en otra terminal (puerto 8099).\n"
            "Vaya a esa terminal, deténgalo con Ctrl+C y vuelva a ejecutar este demo."
        )

p = _proveedor(a.proveedor)
MENSAJES = [{"role": "user", "content": "Responde solo: ok"}]

print(f"\n=== Ronda 1 · SIN protección · {a.n} solicitudes a la vez a {p.nombre} ({p.modelo}) ===")
crudo = openai.OpenAI(api_key=p.api_key, base_url=p.base_url, max_retries=0, timeout=30)


def sin_proteccion(i):
    try:
        crudo.chat.completions.create(model=p.modelo, messages=MENSAJES, max_tokens=256)
        return f"  #{i:02d} [OK] ok"
    except openai.RateLimitError as e:
        return f"  #{i:02d} [ERROR] 429 Too Many Requests - retry-after: {e.response.headers.get('retry-after')}"
    except openai.APIError as e:
        return f"  #{i:02d} [ERROR] {type(e).__name__}"


with ThreadPoolExecutor(a.n) as ex:
    r1 = list(ex.map(sin_proteccion, range(1, a.n + 1)))
print("\n".join(r1))
print(f"-> Fallaron {sum('[ERROR]' in x for x in r1)} de {a.n}. Eso veria su usuario: un error.\n")

if a.proveedor == "simulado":
    servidor_simulado._tiempos.clear()

print("=== Ronda 2 - CON proteccion (ClienteLLM: reintentos + espera exponencial + respaldo) ===")
base = Config(principal=p, respaldo=None, timeout_s=30, max_tokens=256, reintentos=4, razonamiento=None)
try:
    from app.config import cargar_config
    cfg = cargar_config()
    resp = next((x for x in (cfg.principal, cfg.respaldo) if x and x.nombre != p.nombre), None)
    if resp:
        base = dataclasses.replace(base, respaldo=resp)
        print(f"  (respaldo configurado: {resp.nombre})")
    else:
        print("  (sin respaldo: solo reintentos)")
except Exception:
    print("  (sin respaldo configurado en .env)")
llm = ClienteLLM(base)


def con_proteccion(i):
    t = time.monotonic()
    try:
        r = llm.generar_texto("Responde solo: ok", [{"role": "user", "content": "ok"}])
        return f"  #{i:02d} [OK] ok via {r.proveedor} - intento {r.intentos} - {time.monotonic() - t:.1f} s"
    except ErrorLLM as e:
        return f"  #{i:02d} [ERROR] mensaje al usuario: '{e.mensaje_usuario}'"


with ThreadPoolExecutor(a.n) as ex:
    r2 = list(ex.map(con_proteccion, range(1, a.n + 1)))
print("\n".join(r2))
print(f"-> Respondieron {sum('[OK]' in x for x in r2)} de {a.n}. Los detalles quedaron en logs/llm.jsonl")
