import asyncio

import httpx

from app import main


async def request(method: str, url: str, **kwargs):
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, url, **kwargs)


def run(coro):
    return asyncio.run(coro)


def post(url: str, **kwargs):
    return run(request("POST", url, **kwargs))


def get(url: str, **kwargs):
    return run(request("GET", url, **kwargs))


def test_chat_returns_ollama_answer(monkeypatch):
    async def fake_chat_with_ollama(message: str):
        assert message == "What is a local LLM?"
        return {"model": "qwen3:8b", "message": {"content": "A model running on your machine."}}

    monkeypatch.setattr(main, "chat_with_ollama", fake_chat_with_ollama)

    response = post("/chat", json={"message": "What is a local LLM?"})

    assert response.status_code == 200
    assert response.json() == {
        "answer": "A model running on your machine.",
        "model": "qwen3:8b",
    }


def test_chat_rejects_empty_message():
    response = post("/chat", json={"message": ""})

    assert response.status_code == 422


def test_health_reports_ready(monkeypatch):
    async def fake_check_ollama():
        return "ready"

    monkeypatch.setattr(main, "check_ollama", fake_check_ollama)

    response = get("/health")

    assert response.status_code == 200
    assert response.json() == {"api": "ready", "ollama": "ready", "model": "qwen3:8b"}
