import sys
from pathlib import Path
from typing import Literal

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import servidor_simulado

from app.config import Config, Proveedor
from app.schemas import Estricto
from app.services.llm import ClienteLLM


class Simple(Estricto):
    perfil: Literal["conductor_particular", "conductor_profesional", "peaton"]
    situacion: str
    valido: bool


def test_json_por_http_con_429_real():
    srv = servidor_simulado.iniciar(puerto=0, limite=1, ventana=1)
    try:
        prov = Proveedor("simulado", f"http://127.0.0.1:{srv.server_port}/v1", "no-se-necesita", "simulado-1")
        cfg = Config(principal=prov, respaldo=None, timeout_s=5, max_tokens=100, reintentos=4, razonamiento=None)
        llm = ClienteLLM(cfg)
        a = llm.generar_json("sys", "escenario", Simple)
        b = llm.generar_json("sys", "escenario", Simple)
        assert isinstance(a.datos, Simple) and b.intentos >= 2
    finally:
        srv.shutdown()
        srv.server_close()
