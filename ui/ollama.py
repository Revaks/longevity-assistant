# -*- coding: utf-8 -*-
"""Работа с локальной нейросетью Ollama."""

import json
import urllib.request
from dataclasses import dataclass

OLLAMA_URL = "http://localhost:11434"


@dataclass(frozen=True)
class ModelInfo:
    """Модель Ollama и то, что она умеет — поле capabilities из /api/show."""
    name: str
    capabilities: frozenset


def list_models(timeout: int = 3) -> list:
    """Модели Ollama вместе с их возможностями.

    Сначала /api/tags — список имён, затем /api/show на каждое имя — набор
    возможностей (`completion`, `embedding`, ...). Любая сетевая ошибка или
    неожиданный формат ответа дают пустой список, а не исключение —
    приложение обязано полностью работать без Ollama.
    """
    try:
        req = urllib.request.Request(OLLAMA_URL + "/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        raw = data.get("models", [])
        names = [m["name"] for m in raw if isinstance(m, dict) and "name" in m]
    except Exception:
        return []

    return [ModelInfo(name, _capabilities(name, timeout)) for name in names]


def _capabilities(name: str, timeout: int) -> frozenset:
    """Возможности одной модели. Сбой на одной модели не должен ронять весь список —
    поэтому ошибка здесь превращается в пустой набор (модель без capabilities
    ниже в generative() считается пригодной для генерации)."""
    try:
        payload = json.dumps({"name": name}).encode("utf-8")
        req = urllib.request.Request(
            OLLAMA_URL + "/api/show", data=payload,
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        caps = data.get("capabilities", [])
        return frozenset(caps) if isinstance(caps, list) else frozenset()
    except Exception:
        return frozenset()


def generative(models) -> list:
    """Модели, пригодные для генерации. Пустой набор возможностей — старая Ollama."""
    return [m.name for m in models
            if "completion" in m.capabilities or not m.capabilities]


def embedding(models) -> list:
    """Модели, годные только для эмбеддингов — генератору их предлагать нельзя."""
    return [m.name for m in models if "embedding" in m.capabilities]


def ask_ollama(model: str, prompt: str, timeout: int = 180) -> str:
    """Однократный запрос к Ollama /api/generate (stream=false)."""
    payload = json.dumps({"model": model, "prompt": prompt,
                          "stream": False, "options": {"temperature": 0.4}})
    req = urllib.request.Request(
        OLLAMA_URL + "/api/generate", data=payload.encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("response", "").strip()
