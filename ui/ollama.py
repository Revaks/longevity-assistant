# -*- coding: utf-8 -*-
"""Работа с локальной нейросетью Ollama."""

import json
import urllib.request

OLLAMA_URL = "http://localhost:11434"


def ollama_models() -> list:
    """Список доступных моделей Ollama (пусто, если сервис недоступен)."""
    try:
        req = urllib.request.Request(OLLAMA_URL + "/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


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
