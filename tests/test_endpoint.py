import json as _json

from app.main import Problema, _problema, app, crear_escenario, evaluar, health, obtener_llm, progreso
from app.schemas import EscenarioVialSchema, OpcionEscenario, SolicitudEscenario, SolicitudEvaluacion
from app.services.llm import ProveedorNoDisponible, Resultado


class LLMFalso:
    def __init__(self, resultado=None, error=None):
        self.resultado, self.error = resultado, error

    def generar_json(self, system, usuario, esquema):
        if self.error:
            raise self.error
        return self.resultado


class _RespSimple:
    def __init__(self, status_code: int, payload: dict, headers: dict | None = None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}

    def json(self):
        return self._payload


class ClienteDirecto:
    def __init__(self, llm):
        self.llm = llm

    def get(self, ruta: str, headers: dict | None = None):
        if ruta == "/health":
            return _RespSimple(200, health())
        if ruta == "/progreso":
            sesion = (headers or {}).get("X-Session-ID", "ip:127.0.0.1").lower()
            return _RespSimple(200, progreso(sesion=sesion).model_dump())
        raise ValueError(f"Ruta no soportada: {ruta}")

    def post(self, ruta: str, json: dict, headers: dict | None = None):
        sesion = (headers or {}).get("X-Session-ID", "ip:127.0.0.1").lower()
        try:
            if ruta == "/escenarios":
                res = crear_escenario(SolicitudEscenario(**json), sesion=sesion, llm=self.llm)
                return _RespSimple(200, res.model_dump())
            if ruta == "/evaluaciones":
                res = evaluar(SolicitudEvaluacion(**json), sesion=sesion)
                return _RespSimple(200, res.model_dump())
        except Problema as p:
            resp = _problema(p.estado, p.titulo, p.detalle, p.tipo, p.cabeceras)
            return _RespSimple(p.estado, _json.loads(resp.body.decode("utf-8")), dict(resp.headers))
        raise ValueError(f"Ruta no soportada: {ruta}")


def con(llm):
    app.dependency_overrides[obtener_llm] = lambda: llm
    return ClienteDirecto(llm)


def mock_escenario(**kw):
    opciones = [
        OpcionEscenario(id_opcion="A", texto="Acelerar y pasar con semáforo en verde ignorando al agente", es_correcta=False),
        OpcionEscenario(id_opcion="B", texto="Detener la marcha y obedecer la señal manual del agente de tránsito", es_correcta=True),
        OpcionEscenario(id_opcion="C", texto="Girar a la derecha sin colocar la luz direccional para esquivarlo", es_correcta=False),
        OpcionEscenario(id_opcion="D", texto="Tocar la bocina insistentemente para exigir el paso prioritario", es_correcta=False),
    ]
    base = dict(
        id_escenario="ESC-PRUEBA-01",
        perfil="conductor_particular",
        nivel_dificultad="baja",
        situacion="Conduces en una avenida principal y un agente de tránsito te indica detenerte a pesar de tener semáforo verde.",
        opciones=opciones,
        respuesta_correcta="B",
        id_contravencion_asociada="CONT-COIP-ART389-1",
        articulo_norma="Art. 389 num. 1",
        explicacion_educativa="Las indicaciones del agente de tránsito tienen máxima prioridad sobre el semáforo y las señales luminosas fijas.",
    )
    return Resultado(EscenarioVialSchema(**{**base, **kw}), "a", "gemini-3.8-flash", 120, 80, 250, 1)


def test_health():
    assert con(LLMFalso()).get("/health").json() == {"estado": "ok"}


def test_generar_escenario_oculta_respuesta_correcta():
    client = con(LLMFalso(mock_escenario()))
    headers = {"X-Session-ID": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"}
    r = client.post("/escenarios", json={"perfil": "conductor_particular", "nivel_dificultad": "baja"}, headers=headers)
    assert r.status_code == 200
    datos = r.json()
    assert "id_escenario" in datos
    assert len(datos["opciones"]) == 4
    assert "respuesta_correcta" not in datos
    assert "id_contravencion_asociada" not in datos
    assert "explicacion_educativa" not in datos


def test_evaluar_respuesta_correcta_e_incorrecta():
    client = con(LLMFalso(mock_escenario()))
    headers = {"X-Session-ID": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"}
    creado = client.post("/escenarios", json={"perfil": "conductor_particular", "nivel_dificultad": "baja"}, headers=headers).json()
    id_esc = creado["id_escenario"]

    r_eval = client.post("/evaluaciones", json={"id_escenario": id_esc, "respuesta": "A"}, headers=headers)
    assert r_eval.status_code == 200
    res = r_eval.json()
    assert res["es_correcta"] is False
    assert res["respuesta_correcta"] == "B"
    assert res["sancion"]["multa_usd"] == 144.60
    assert res["sancion"]["puntos_reducidos"] == 6.0
    assert res["sancion"]["puntos_aplicables"] == 0.0
    assert res["contravencion"]["articulo"] == "Art. 389 num. 1"


def test_evaluacion_no_permite_reusar_escenario():
    client = con(LLMFalso(mock_escenario()))
    headers = {"X-Session-ID": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"}
    creado = client.post("/escenarios", json={"perfil": "conductor_particular", "nivel_dificultad": "baja"}, headers=headers).json()
    id_esc = creado["id_escenario"]

    r1 = client.post("/evaluaciones", json={"id_escenario": id_esc, "respuesta": "B"}, headers=headers)
    assert r1.status_code == 200
    assert r1.json()["es_correcta"] is True

    r2 = client.post("/evaluaciones", json={"id_escenario": id_esc, "respuesta": "B"}, headers=headers)
    assert r2.status_code == 404


def test_fuera_de_dominio_retorna_422_rfc9457():
    abstencion = mock_escenario(
        id_contravencion_asociada="FALTA",
        situacion="FALTA: Información fuera del dominio normativo vial de Ecuador",
        opciones=[],
    )
    client = con(LLMFalso(abstencion))
    headers = {"X-Session-ID": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"}
    r = client.post(
        "/escenarios",
        json={"perfil": "conductor_particular", "nivel_dificultad": "baja", "tema": "receta de cocina"},
        headers=headers,
    )
    assert r.status_code == 422
    assert "fuera-de-dominio" in r.json()["type"]


def test_proveedor_caido_retorna_503_con_retry_after():
    client = con(LLMFalso(error=ProveedorNoDisponible()))
    headers = {"X-Session-ID": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"}
    r = client.post("/escenarios", json={"perfil": "conductor_particular", "nivel_dificultad": "baja"}, headers=headers)
    assert r.status_code == 503
    assert "retry-after" in {k.lower() for k in r.headers}


def test_evaluacion_registra_progreso_usuario():
    client = con(LLMFalso(mock_escenario()))
    headers = {"X-Session-ID": "progreso-test-user-01"}
    creado = client.post("/escenarios", json={"perfil": "conductor_particular", "nivel_dificultad": "baja"}, headers=headers).json()
    r_eval = client.post("/evaluaciones", json={"id_escenario": creado["id_escenario"], "respuesta": "B"}, headers=headers).json()
    assert r_eval["progreso"]["aciertos"] >= 1
    prog = client.get("/progreso", headers=headers).json()
    assert prog["total_evaluados"] >= 1 and prog["aciertos"] >= 1
