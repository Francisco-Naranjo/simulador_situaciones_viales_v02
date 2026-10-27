"""Pruebas de las herramientas deterministas: sanción, tabla canónica, validación y evaluación.
Ninguna llama al modelo."""
import json

import pytest
from pydantic import ValidationError

from app.parametros import cargar_parametros
from app.schemas import Contravencion, EscenarioVialSchema
from app.tools.calcular_sancion import calcular_multa, calcular_sancion
from app.tools.contravenciones import (EscenarioInvalido, FueraDeDominio, candidatas, cargar_tabla,
                                       validar_escenario)
from app.tools.evaluar_respuesta import evaluar_respuesta

PARAMS = {"sbu_usd": 460.00, "sbu_fuente": "prueba", "aviso_educativo": "Material educativo."}
CUARTA = Contravencion(id_contravencion="CONT-PRUEBA-1", clase="Cuarta Clase", articulo="Art. 389 num. 1",
                       norma="Código Orgánico Integral Penal", descripcion_infraccion="Desobedecer al agente.",
                       porcentaje_sbu=30.0, puntos_reducidos=6.0,
                       perfiles_aplicables=["conductor_particular", "conductor_profesional"])
TABLA = {CUARTA.id_contravencion: CUARTA}


def escenario(**kw):
    base = dict(
        id_escenario="ESC-X", perfil="conductor_particular", nivel_dificultad="baja",
        situacion="Un agente de tránsito te ordena detenerte con el semáforo en verde.",
        opciones=[{"id_opcion": l, "texto": f"Opción de prueba {l}", "es_correcta": l == "B"} for l in "ABCD"],
        respuesta_correcta="B", id_contravencion_asociada="CONT-PRUEBA-1", articulo_norma="Art. 389 num. 1",
        explicacion_educativa="Las señales del agente prevalecen sobre el semáforo.")
    return EscenarioVialSchema(**{**base, **kw})


# ------------------------------------------------------------ HU-02 · cálculo determinista
def test_hu02_cuarta_clase_30_por_ciento_de_460_es_138():
    s = calcular_sancion(CUARTA, PARAMS)
    assert s.multa_usd == 138.00 and s.puntos_reducidos == 6.0 and s.sbu_usd == 460.00


@pytest.mark.parametrize("porcentaje,sbu,esperado", [
    (100, 460, "460.00"), (50, 460, "230.00"), (15, 460, "69.00"), (5, 470, "23.50"), (10, 482, "48.20"),
    (40, 460.0, "184.00"), (0, 460, "0.00"),
])
def test_multa_exacta_con_decimal(porcentaje, sbu, esperado):
    assert str(calcular_multa(porcentaje, sbu)) == esperado


@pytest.mark.parametrize("porcentaje,sbu", [(-1, 460), (101, 460), (30, 0), (30, -460)])
def test_multa_rechaza_valores_imposibles(porcentaje, sbu):
    with pytest.raises(ValueError):
        calcular_multa(porcentaje, sbu)


def test_cambiar_sbu_en_configuracion_cambia_la_multa(monkeypatch):
    """Prueba mínima del caso 08: el 100 % de las sanciones usa el SBU leído de configuración."""
    from pathlib import Path
    monkeypatch.setattr(Path, "read_text", lambda self, encoding="utf-8": json.dumps({"sbu_usd": 500.0, "aviso_educativo": "x"}))
    assert calcular_sancion(CUARTA, cargar_parametros()).multa_usd == 150.00


def test_parametros_rechaza_sbu_invalido(monkeypatch):
    from pathlib import Path
    monkeypatch.setattr(Path, "read_text", lambda self, encoding="utf-8": json.dumps({"sbu_usd": "cuatrocientos"}))
    with pytest.raises(ValueError, match="sbu_usd"):
        cargar_parametros()


# ------------------------------------------------------------ tabla canónica
def test_tabla_real_carga_y_es_coherente():
    tabla = cargar_tabla()
    assert len(tabla) == 90
    for c in tabla.values():
        assert c.id_contravencion.startswith("CONT-") and c.articulo.startswith("Art.")
    for perfil in ("conductor_particular", "conductor_profesional", "motociclista", "ciclista", "peaton"):
        assert candidatas(perfil, tabla), f"no hay contravenciones para {perfil}"


def test_misma_clase_misma_sancion_en_la_tabla():
    """En el COIP la sanción económica depende estrictamente de la CLASE (porcentaje SBU).
    Los puntos de licencia son fijos por clase para conductores; para peatones y ciclistas es 0 (Art. 373 COIP).
    Además, tras la reforma RO 512 (2021), puntos_aplicables es 0 de la 3.ª a la 7.ª clase."""
    porcentaje_por_clase = {}
    for c in cargar_tabla().values():
        porcentaje_por_clase.setdefault((c.norma, c.clase), set()).add(c.porcentaje_sbu)
        if set(c.perfiles_aplicables).issubset({"peaton", "ciclista"}):
            assert c.puntos_reducidos == 0.0, "Peatones y ciclistas no pierden puntos de licencia"
        elif c.clase == "Séptima Clase":
            assert c.puntos_reducidos == 1.5, "El texto del Art. 392 prevé 1.5 puntos para conductores"
            assert c.puntos_aplicables == 0.0, "La reforma de 2021 suprimió la reducción de puntos en 7ma clase"
    assert all(len(v) == 1 for v in porcentaje_por_clase.values()), porcentaje_por_clase


# ------------------------------------------------------------ HU-01 · validación del escenario
def test_hu01_escenario_valido_devuelve_la_contravencion_canonica():
    assert validar_escenario(escenario(), "conductor_particular", "baja", TABLA) is CUARTA


def test_contravencion_inexistente_se_descarta():
    with pytest.raises(EscenarioInvalido, match="inexistente"):
        validar_escenario(escenario(id_contravencion_asociada="CONT-INVENTADA-99"), "conductor_particular", "baja", TABLA)


def test_contravencion_de_otro_perfil_se_descarta():
    with pytest.raises(EscenarioInvalido, match="perfil"):
        validar_escenario(escenario(perfil="peaton"), "peaton", "baja", TABLA)


def test_dificultad_distinta_a_la_pedida_se_descarta():
    with pytest.raises(EscenarioInvalido):
        validar_escenario(escenario(nivel_dificultad="alta"), "conductor_particular", "baja", TABLA)


def test_marca_falta_es_abstencion():
    esc = escenario(id_contravencion_asociada="FALTA",
                    situacion="FALTA: Información fuera del dominio normativo vial de Ecuador", opciones=[])
    with pytest.raises(FueraDeDominio):
        validar_escenario(esc, "conductor_particular", "baja", TABLA)


@pytest.mark.parametrize("cambio", [
    {"opciones": [{"id_opcion": l, "texto": f"Opción de prueba {l}", "es_correcta": l == "A"} for l in "ABC"]},
    {"respuesta_correcta": "C"},
    {"opciones": [{"id_opcion": l, "texto": f"Opción de prueba {l}", "es_correcta": True} for l in "ABCD"]},
    {"situacion": "corta"},
    {"campo_inventado": "x"},
])
def test_esquema_rechaza_escenarios_incoherentes(cambio):
    with pytest.raises(ValidationError):
        escenario(**cambio)


# ------------------------------------------------------------ evaluación
def test_respuesta_incorrecta_muestra_sancion_calculada():
    r = evaluar_respuesta(escenario(), CUARTA, "A", PARAMS)
    assert r.es_correcta is False and r.respuesta_correcta == "B"
    assert r.sancion.multa_usd == 138.00 and r.contravencion.articulo == "Art. 389 num. 1"


def test_respuesta_correcta():
    assert evaluar_respuesta(escenario(), CUARTA, "B", PARAMS).es_correcta is True
