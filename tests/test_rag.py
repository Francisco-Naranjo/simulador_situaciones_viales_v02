"""Pruebas automatizadas del sistema RAG · Módulo 3 (Caso 08 «Vía Segura»)."""
import asyncio
import json
from pathlib import Path

from app.main import buscar_rag
from app.services.rag import MENSAJE_ABSTENCION_RAG, cargar_indice, recuperar
from scripts.evaluar_rag import evaluar

RAIZ = Path(__file__).resolve().parent.parent


def test_indice_rag_sin_fragmentos_huerfanos():
    """Misión 2: el corte por estructura `(?=Art.\\s*\\d+)` no debe producir fragmentos huérfanos."""
    ruta = RAIZ / "data" / "processed" / "indice_rag.json"
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    assert datos["huerfanos"] == 0
    assert datos["total_fragmentos"] >= 600
    for f in cargar_indice():
        assert f["texto"].startswith("Art."), f"Fragmento huérfano detectado: {f['id']}"
        assert {"documento", "articulo", "clase", "puntos", "vigente"} <= set(f["metadatos"].keys())


def test_filtro_vigencia_excluye_infracciones_derogadas_lotttsv_2011():
    """Misión 3: el filtro `vigente='true'` se aplica antes del top-k para no citar artículos derogados."""
    r = recuperar("contravenciones de tránsito semáforo en rojo", top_k=5)
    assert not r.abstencion
    for frag in r.fragmentos:
        assert frag.metadatos["vigente"] == "true"
    assert r.fragmentos[0].metadatos["documento"] == "COIP"
    assert r.fragmentos[0].metadatos["articulo"] == "389"


def test_evaluacion_20_preguntas_hit_at_5_y_silencio():
    """Misión 4 y 5: verifica Hit@5 >= 90% y precisión de abstención = 100% sobre eval/preguntas.json."""
    res = evaluar()
    assert res["total_preguntas"] == 20
    assert res["hit_at_5"] == 1.0
    assert res["hit_at_1"] == 1.0
    assert res["precision_silencio"] == 1.0


def test_regla_de_silencio_ante_consulta_fuera_de_alcance_o_administrativa():
    """Misión 5: o cita la fuente o guarda silencio."""
    r_deriva = recuperar("¿Me pueden quitar la licencia por acumular puntos de hace 6 años?")
    assert r_deriva.abstencion is True
    assert r_deriva.mensaje_abstencion == MENSAJE_ABSTENCION_RAG
    assert r_deriva.fragmentos == []


def test_endpoint_rag_buscar():
    cuerpo = buscar_rag(q="celular manejando sin manos libres", top_k=3)
    assert cuerpo["abstencion"] is False
    assert cuerpo["cita_principal"] == "COIP, Art. 391"
