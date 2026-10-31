import pytest

from app.config import ErrorConfiguracion, cargar_config

LIMPIAR = [
    "LLM_PRINCIPAL", "LLM_RESPALDO", "LLM_PROVIDER", "LLM_FALLBACK_PROVIDER",
    "GEMINI_API_KEY", "GROQ_API_KEY", "GEMINI_MODEL", "GROQ_MODEL",
    "LLM_MODEL", "LLM_FALLBACK_MODEL", "LLM_TIMEOUT_S", "LLM_TIMEOUT_SECONDS",
    "LLM_MAX_TOKENS", "LLM_MAX_OUTPUT_TOKENS", "LLM_REINTENTOS", "LLM_RAZONAMIENTO",
]


@pytest.fixture(autouse=True)
def entorno_limpio(monkeypatch):
    for v in LIMPIAR:
        monkeypatch.delenv(v, raising=False)


def test_nombres_del_kit(monkeypatch):
    monkeypatch.setenv("LLM_PRINCIPAL", "simulado")
    monkeypatch.setenv("LLM_RESPALDO", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "x")
    cfg = cargar_config()
    assert cfg.principal.nombre == "simulado" and cfg.respaldo.nombre == "groq"
    assert cfg.reintentos == 3 and cfg.timeout_s == 30


def test_nombres_de_la_clase_1(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "x")
    monkeypatch.setenv("LLM_MODEL", "modelo-del-principal")
    monkeypatch.setenv("LLM_FALLBACK_PROVIDER", "simulado")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "20")
    monkeypatch.setenv("LLM_MAX_OUTPUT_TOKENS", "999")
    cfg = cargar_config()
    assert cfg.principal.nombre == "groq" and cfg.principal.modelo == "modelo-del-principal"
    assert cfg.respaldo.nombre == "simulado"
    assert cfg.timeout_s == 20 and cfg.max_tokens == 999


def test_linea_vacia_usa_el_valor_por_defecto(monkeypatch):
    monkeypatch.setenv("LLM_PRINCIPAL", "simulado")
    monkeypatch.setenv("LLM_REINTENTOS", "")
    monkeypatch.setenv("LLM_RESPALDO", "")
    cfg = cargar_config()
    assert cfg.reintentos == 3 and cfg.respaldo is None


def test_numero_mal_escrito_da_mensaje_claro(monkeypatch):
    monkeypatch.setenv("LLM_PRINCIPAL", "simulado")
    monkeypatch.setenv("LLM_TIMEOUT_S", "abc")
    with pytest.raises(ErrorConfiguracion, match="LLM_TIMEOUT_S.*abc"):
        cargar_config()


def test_razonamiento_none_e_invalido(monkeypatch):
    monkeypatch.setenv("LLM_PRINCIPAL", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setenv("LLM_RAZONAMIENTO", "none")
    assert cargar_config().razonamiento is None
    monkeypatch.setenv("LLM_RAZONAMIENTO", "médium")
    with pytest.raises(ErrorConfiguracion, match="LLM_RAZONAMIENTO"):
        cargar_config()
