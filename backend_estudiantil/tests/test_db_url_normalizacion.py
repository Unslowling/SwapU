import pytest

from backend_estudiantil.adapters.db import _normalizar_url, get_engine

pytestmark = pytest.mark.unit


def test_url_neon_con_sslmode_se_adapta_a_asyncpg():
    url, args = _normalizar_url("postgresql://u:p@ep-x.neon.tech/swapu?sslmode=require&channel_binding=require")
    assert url == "postgresql+asyncpg://u:p@ep-x.neon.tech/swapu"
    assert args == {"ssl": "require"}


def test_url_estilo_heroku_postgres():
    url, args = _normalizar_url("postgres://u:p@host:5432/db")
    assert url == "postgresql+asyncpg://u:p@host:5432/db"
    assert args == {}


def test_url_asyncpg_local_no_cambia():
    assert _normalizar_url("postgresql+asyncpg://u:p@localhost:5432/swapu") == (
        "postgresql+asyncpg://u:p@localhost:5432/swapu", {})


def test_get_engine_reutiliza_el_motor():
    assert get_engine() is get_engine()
