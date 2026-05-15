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
    async def fake_chat_with_tools_and_history(message: str, history: list):
        assert message == "What is a local LLM?"
        assert history == []
        return {"model": "qwen3:8b", "message": {"content": "A model running on your machine."}}, []

    monkeypatch.setattr(main, "chat_with_tools_and_history", fake_chat_with_tools_and_history)

    response = post("/chat", json={"message": "What is a local LLM?"})

    assert response.status_code == 200
    assert response.json() == {
        "answer": "A model running on your machine.",
        "model": "qwen3:8b",
        "used_tools": False,
        "tool_names": [],
        "status": "answered_without_tool",
        "trace": [],
    }


def test_chat_runs_weather_tool_and_returns_trace(monkeypatch):
    calls = []

    async def fake_post_ollama_chat(payload: dict):
        calls.append(payload)
        if len(calls) == 1:
            return {
                "model": "qwen3:8b",
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "get_weather",
                                "arguments": {
                                    "cities": ["Seattle", "New York City", "Los Angeles", "Pittsburgh"]
                                },
                            }
                        }
                    ],
                },
            }
        return {
            "model": "qwen3:8b",
            "message": {
                "content": (
                    "Fake weather is available for Seattle, New York City, and Los Angeles. "
                    "I do not have weather available for Pittsburgh."
                )
            },
        }

    monkeypatch.setattr(main, "post_ollama_chat", fake_post_ollama_chat)

    response = post(
        "/chat",
        json={"message": "What is the weather in Seattle, New York City, Los Angeles, and Pittsburgh?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == (
        "Fake weather is available for Seattle, New York City, and Los Angeles. "
        "I do not have weather available for Pittsburgh."
    )
    assert body["model"] == "qwen3:8b"
    assert body["used_tools"] is True
    assert body["tool_names"] == ["get_weather"]
    assert body["status"] == "answered_with_tool"
    assert [event["type"] for event in body["trace"]] == [
        "ollama_request",
        "ollama_response",
        "tool_request",
        "tool_response",
        "ollama_request",
        "ollama_response",
    ]
    assert body["trace"][2] == {
        "type": "tool_request",
        "name": "get_weather",
        "payload": {"cities": ["Seattle", "New York City", "Los Angeles", "Pittsburgh"]},
    }
    assert body["trace"][3]["payload"]["source"] == "fake-weather-v0"
    assert [forecast["city"] for forecast in body["trace"][3]["payload"]["forecasts"]] == [
        "Seattle",
        "New York City",
        "Los Angeles",
    ]
    assert body["trace"][3]["payload"]["unavailable_cities"] == ["Pittsburgh"]
    assert body["trace"][3]["payload"]["supported_cities"] == [
        "Seattle",
        "New York City",
        "Los Angeles",
    ]
    assert calls[0]["tools"][0]["function"]["name"] == "get_weather"
    assert calls[1]["messages"][-1]["role"] == "tool"


def test_chat_sends_history_to_ollama(monkeypatch):
    calls = []

    async def fake_post_ollama_chat(payload: dict):
        calls.append(payload)
        return {
            "model": "qwen3:8b",
            "message": {"content": "Seattle is still in the previous weather context."},
        }

    monkeypatch.setattr(main, "post_ollama_chat", fake_post_ollama_chat)

    response = post(
        "/chat",
        json={
            "message": "What about tomorrow?",
            "history": [
                {"role": "user", "content": "What is the weather in Seattle?"},
                {"role": "assistant", "content": "Fake weather in Seattle is light rain."},
            ],
        },
    )

    assert response.status_code == 200
    assert calls[0]["messages"][-3:] == [
        {"role": "user", "content": "What is the weather in Seattle?"},
        {"role": "assistant", "content": "Fake weather in Seattle is light rain."},
        {"role": "user", "content": "What about tomorrow?"},
    ]
    assert response.json()["status"] == "answered_without_tool"


def test_get_weather_reports_unsupported_cities():
    weather = main.get_weather(["Seattle", "Chicago", "Los Angeles"])

    assert [forecast["city"] for forecast in weather["forecasts"]] == ["Seattle", "Los Angeles"]
    assert weather["unavailable_cities"] == ["Chicago"]
    assert weather["supported_cities"] == ["Seattle", "New York City", "Los Angeles"]


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
