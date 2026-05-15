import os
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    answer: str
    model: str


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


async def check_ollama() -> str:
    try:
        async with httpx.AsyncClient(base_url=get_ollama_base_url(), timeout=5.0) as client:
            response = await client.get("/api/version")
            response.raise_for_status()
            return "ready"
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"Ollama is unavailable: {exc}") from exc


async def chat_with_ollama(message: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": get_ollama_model(),
        "messages": [{"role": "user", "content": message}],
        "stream": False,
        "think": get_ollama_think(),
    }

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


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    ollama_status = await check_ollama()
    return HealthResponse(api="ready", ollama=ollama_status, model=get_ollama_model())


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    data = await chat_with_ollama(request.message)
    answer = data.get("message", {}).get("content")
    if not isinstance(answer, str) or not answer:
        raise HTTPException(status_code=502, detail="Ollama returned an empty response")
    return ChatResponse(answer=answer, model=str(data.get("model") or get_ollama_model()))
