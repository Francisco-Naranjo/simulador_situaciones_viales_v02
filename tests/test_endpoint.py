"""Pruebas del endpoint con el servicio de IA reemplazado por un doble."""
from fastapi.testclient import TestClient

from app.main import app, obtener_llm
from app.schemas import EscenarioVialSchema, OpcionEscenario
from app.services.llm import ProveedorNoDisponible, Resultado, SalidaInvalida


class LLMFalso:
    def __init__(self, resultado=None, error=None):
        self.resultado, self.error = resultado, error

    def generar_json(self, system, usuario, esquema):
        if self.error:
            raise self.error
        return self.resultado


def con(llm):
    app.dependency_overrides[obtener_llm] = lambda: llm
    return TestClient(app)


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
    # La respuesta correcta y la contravención NO deben revelarse antes de que el usuario responda
    assert "respuesta_correcta" not in datos
    assert "id_contravencion_asociada" not in datos
    assert "explicacion_educativa" not in datos


def test_evaluar_respuesta_correcta_e_incorrecta():
    client = con(LLMFalso(mock_escenario()))
    headers = {"X-Session-ID": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"}
    creado = client.post("/escenarios", json={"perfil": "conductor_particular", "nivel_dificultad": "baja"}, headers=headers).json()
    id_esc = creado["id_escenario"]

    # Respuesta incorrecta: A
    r_eval = client.post("/evaluaciones", json={"id_escenario": id_esc, "respuesta": "A"}, headers=headers)
    assert r_eval.status_code == 200
    res = r_eval.json()
    assert res["es_correcta"] is False
    assert res["respuesta_correcta"] == "B"
    assert res["sancion"]["multa_usd"] == 144.60  # 30% SBU ($482.00)
    assert res["sancion"]["puntos_reducidos"] == 6.0
    assert res["sancion"]["puntos_aplicables"] == 0.0  # Reforma RO 512 (2021)
    assert res["contravencion"]["articulo"] == "Art. 389 num. 1"


def test_evaluacion_no_permite_reusar_escenario():
    client = con(LLMFalso(mock_escenario()))
    headers = {"X-Session-ID": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"}
    creado = client.post("/escenarios", json={"perfil": "conductor_particular", "nivel_dificultad": "baja"}, headers=headers).json()
    id_esc = creado["id_escenario"]

    # Primer intento funciona
    r1 = client.post("/evaluaciones", json={"id_escenario": id_esc, "respuesta": "B"}, headers=headers)
    assert r1.status_code == 200
    assert r1.json()["es_correcta"] is True

    # Segundo intento con el mismo escenario da 404
    r2 = client.post("/evaluaciones", json={"id_escenario": id_esc, "respuesta": "B"}, headers=headers)
    assert r2.status_code == 404


def test_fuera_de_dominio_retorna_422_rfc9457():
    # El modelo se abstiene con la marca FALTA
    abstencion = mock_escenario(
        id_contravencion_asociada="FALTA",
        situacion="FALTA: Información fuera del dominio normativo vial de Ecuador",
        opciones=[]
    )
    client = con(LLMFalso(abstencion))
    headers = {"X-Session-ID": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"}
    r = client.post("/escenarios", json={"perfil": "conductor_particular", "nivel_dificultad": "baja", "tema": "receta de cocina"}, headers=headers)
    assert r.status_code == 422
    assert "fuera-de-dominio" in r.json()["type"]


def test_proveedor_caido_retorna_503_con_retry_after():
    client = con(LLMFalso(error=ProveedorNoDisponible()))
    headers = {"X-Session-ID": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"}
    r = client.post("/escenarios", json={"perfil": "conductor_particular", "nivel_dificultad": "baja"}, headers=headers)
    assert r.status_code == 503
    assert "Retry-After" in r.headers
