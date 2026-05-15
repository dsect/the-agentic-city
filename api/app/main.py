import json
import os
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


GET_WEATHER_TOOL = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get the current weather for one or more supported cities.",
        "parameters": {
            "type": "object",
            "properties": {
                "cities": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Cities to check. Supported cities are Seattle, New York City, and Los Angeles.",
                }
            },
            "required": ["cities"],
        },
    },
}

SYSTEM_PROMPT = (
    "You are a local assistant for The Agentic City workbench. "
    "When the user asks about weather, call the get_weather tool before answering. "
    "The weather tool only supports Seattle, New York City, and Los Angeles. "
    "If the tool reports unavailable cities, tell the user weather is not available for those cities "
    "and suggest trying one of the supported cities. "
    "After the tool result arrives, summarize it plainly and mention that the weather data is fake."
)

SUPPORTED_WEATHER: dict[str, dict[str, Any]] = {
    "seattle": {
        "city": "Seattle",
        "condition": "light rain with low clouds",
        "temperature_f": 58,
        "humidity_percent": 82,
        "wind_mph": 9,
    },
    "new york city": {
        "city": "New York City",
        "condition": "clear and brisk between tall buildings",
        "temperature_f": 64,
        "humidity_percent": 55,
        "wind_mph": 12,
    },
    "los angeles": {
        "city": "Los Angeles",
        "condition": "sunny with a light coastal haze",
        "temperature_f": 74,
        "humidity_percent": 46,
        "wind_mph": 6,
    },
}


class ConversationMessage(BaseModel):
    role: str
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    history: list[ConversationMessage] = Field(default_factory=list, max_length=20)


class ToolTraceEvent(BaseModel):
    type: str
    name: str | None = None
    payload: dict[str, Any]


class ChatResponse(BaseModel):
    answer: str
    model: str
    used_tools: bool
    tool_names: list[str] = Field(default_factory=list)
    status: str
    trace: list[ToolTraceEvent] = Field(default_factory=list)


class HealthResponse(BaseModel):
    api: str
    ollama: str
    model: str


app = FastAPI(title="The Agentic City API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def get_ollama_base_url() -> str:
    return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")


def get_ollama_model() -> str:
    return os.getenv("OLLAMA_MODEL", "qwen3:8b")


def get_ollama_think() -> bool:
    return os.getenv("OLLAMA_THINK", "false").lower() in {"1", "true", "yes", "on"}


def normalize_city(city: str) -> str:
    return " ".join(city.lower().replace(",", " ").replace(".", " ").split())


def get_weather(cities: list[str]) -> dict[str, Any]:
    requested_cities = [city.strip() for city in cities if city.strip()]
    forecasts = []
    unavailable = []

    for city in requested_cities:
        forecast = SUPPORTED_WEATHER.get(normalize_city(city))
        if forecast is None:
            unavailable.append(city)
        else:
            forecasts.append(forecast)

    return {
        "forecasts": forecasts,
        "unavailable_cities": unavailable,
        "supported_cities": [forecast["city"] for forecast in SUPPORTED_WEATHER.values()],
        "message": (
            "Weather is only available for Seattle, New York City, and Los Angeles."
            if unavailable
            else "Weather is available for every requested city."
        ),
        "source": "fake-weather-v0",
    }


def serialize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload, default=str))


def parse_tool_arguments(arguments: Any) -> dict[str, Any]:
    if isinstance(arguments, dict):
        return arguments
    if isinstance(arguments, str) and arguments.strip():
        try:
            parsed = json.loads(arguments)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=502, detail=f"Ollama returned invalid tool arguments: {arguments}") from exc
        if isinstance(parsed, dict):
            return parsed
    return {}


def parse_weather_cities(arguments: dict[str, Any]) -> list[str]:
    cities = arguments.get("cities")
    if isinstance(cities, list):
        return [str(city) for city in cities]

    location = arguments.get("location")
    if isinstance(location, list):
        return [str(city) for city in location]
    if isinstance(location, str):
        return [location]

    city = arguments.get("city")
    if isinstance(city, str):
        return [city]

    return ["Unknown"]


def extract_answer(data: dict[str, Any]) -> str:
    answer = data.get("message", {}).get("content")
    if not isinstance(answer, str) or not answer:
        raise HTTPException(status_code=502, detail="Ollama returned an empty response")
    return answer


def summarize_trace(trace: list[ToolTraceEvent]) -> tuple[bool, list[str], str]:
    tool_names = []
    for event in trace:
        if event.type == "tool_request" and event.name and event.name not in tool_names:
            tool_names.append(event.name)

    if tool_names:
        return True, tool_names, "answered_with_tool"
    return False, [], "answered_without_tool"


async def check_ollama() -> str:
    try:
        async with httpx.AsyncClient(base_url=get_ollama_base_url(), timeout=5.0) as client:
            response = await client.get("/api/version")
            response.raise_for_status()
            return "ready"
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"Ollama is unavailable: {exc}") from exc


async def post_ollama_chat(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(base_url=get_ollama_base_url(), timeout=120.0) as client:
            response = await client.post("/api/chat", json=payload)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text or exc.response.reason_phrase
        raise HTTPException(status_code=502, detail=f"Ollama chat failed: {detail}") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"Ollama is unavailable: {exc}") from exc


def build_conversation(history: list[ConversationMessage], message: str) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for item in history:
        if item.role not in {"user", "assistant"}:
            continue
        messages.append({"role": item.role, "content": item.content})
    messages.append({"role": "user", "content": message})
    return messages


async def chat_with_tools_and_history(
    message: str, history: list[ConversationMessage]
) -> tuple[dict[str, Any], list[ToolTraceEvent]]:
    messages = build_conversation(history, message)
    trace: list[ToolTraceEvent] = []
    payload: dict[str, Any] = {
        "model": get_ollama_model(),
        "messages": messages,
        "stream": False,
        "think": get_ollama_think(),
        "tools": [GET_WEATHER_TOOL],
    }

    trace.append(ToolTraceEvent(type="ollama_request", payload=serialize_payload(payload)))
    first_response = await post_ollama_chat(payload)
    trace.append(ToolTraceEvent(type="ollama_response", payload=serialize_payload(first_response)))

    assistant_message = first_response.get("message", {})
    tool_calls = assistant_message.get("tool_calls")
    if not isinstance(tool_calls, list) or not tool_calls:
        return first_response, trace

    messages.append(assistant_message)
    for tool_call in tool_calls:
        function = tool_call.get("function", {}) if isinstance(tool_call, dict) else {}
        tool_name = function.get("name")
        arguments = parse_tool_arguments(function.get("arguments"))
        trace.append(
            ToolTraceEvent(
                type="tool_request",
                name=tool_name if isinstance(tool_name, str) else None,
                payload=serialize_payload(arguments),
            )
        )

        if tool_name != "get_weather":
            tool_result = {"error": f"Unknown tool: {tool_name}"}
        else:
            tool_result = get_weather(parse_weather_cities(arguments))

        trace.append(
            ToolTraceEvent(
                type="tool_response",
                name=tool_name if isinstance(tool_name, str) else None,
                payload=serialize_payload(tool_result),
            )
        )
        messages.append(
            {
                "role": "tool",
                "name": tool_name,
                "content": json.dumps(tool_result),
            }
        )

    followup_payload: dict[str, Any] = {
        "model": get_ollama_model(),
        "messages": messages,
        "stream": False,
        "think": get_ollama_think(),
    }
    trace.append(ToolTraceEvent(type="ollama_request", payload=serialize_payload(followup_payload)))
    final_response = await post_ollama_chat(followup_payload)
    trace.append(ToolTraceEvent(type="ollama_response", payload=serialize_payload(final_response)))
    return final_response, trace


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    ollama_status = await check_ollama()
    return HealthResponse(api="ready", ollama=ollama_status, model=get_ollama_model())


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    data, trace = await chat_with_tools_and_history(request.message, request.history)
    used_tools, tool_names, status = summarize_trace(trace)
    return ChatResponse(
        answer=extract_answer(data),
        model=str(data.get("model") or get_ollama_model()),
        used_tools=used_tools,
        tool_names=tool_names,
        status=status,
        trace=trace,
    )
