import pytest

from app import create_app
from app.ai import router
from app.ai.providers import mock


@pytest.fixture(autouse=True)
def ai_mock(tmp_path, monkeypatch):
    """Force mock_jev / mock_llm, temp config and log. No network, no real tokens."""
    monkeypatch.setenv("SOMAARI_AI_MOCK", "1")
    monkeypatch.setenv("SOMAARI_CONFIG", str(tmp_path / "config.toml"))
    monkeypatch.setenv("SOMAARI_AI_LOG", str(tmp_path / "ai.log"))
    router._cache.clear()
    mock.RESPONDER = mock.LLM_RESPONDER = None
    mock.CALLS.clear()
    yield


@pytest.fixture
def client(tmp_path):
    return create_app(db_path=tmp_path / "test.db").test_client()
