import json
from unittest.mock import patch

from ui.ollama import ModelInfo, embedding, generative, list_models


def _response(payload):
    class FakeResponse:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return json.dumps(payload).encode("utf-8")
    return FakeResponse()


def test_splits_models_by_capability():
    models = [
        ModelInfo("qwen3.5:4b", frozenset({"completion", "tools"})),
        ModelInfo("qwen3-embedding:0.6b", frozenset({"embedding"})),
        ModelInfo("qwen3-coder:30b", frozenset({"completion"})),
    ]

    assert generative(models) == ["qwen3.5:4b", "qwen3-coder:30b"]
    assert embedding(models) == ["qwen3-embedding:0.6b"]


def test_embedding_model_never_offered_for_generation():
    models = [ModelInfo("nomic-embed-text", frozenset({"embedding"}))]

    assert generative(models) == []


def test_unreachable_service_returns_empty_list():
    with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
        assert list_models() == []


def test_malformed_response_returns_empty_list():
    with patch("urllib.request.urlopen", return_value=_response({"unexpected": 1})):
        assert list_models() == []


def test_model_without_capabilities_is_treated_as_generative():
    """Старые сборки Ollama не отдают capabilities — не терять такие модели."""
    models = [ModelInfo("llama3", frozenset())]

    assert generative(models) == ["llama3"]
