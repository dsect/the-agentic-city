# the-agentic-city

Model a city for demonstrating AI and agentic capabilities.

This repo currently scaffolds a local LLM web app:

- React + Vite + TypeScript frontend
- Python FastAPI backend
- Ollama running locally in Docker Compose
- Qwen3 model pulled automatically at startup
- Dozzle for browsing container logs

## Prerequisites

- Docker with Docker Compose v2
- Enough disk space for the default model, `qwen3:8b` (about 5.2 GB)
- For GPU acceleration on WSL2/Windows 11: a current NVIDIA Windows driver, Docker Desktop
  WSL integration, and Docker's NVIDIA runtime support

## Run

```sh
docker compose up --build
```

First startup can take several minutes because Compose waits for Ollama and pulls `qwen3:8b`
before starting the API. The model is stored in the `ollama-data` Docker volume, so later
starts reuse the downloaded model.

Open:

- Web app: http://localhost:5173
- API health: http://localhost:8000/health
- Ollama API: http://localhost:11434
- Dozzle logs: http://localhost:9999

## How It Works

`docker-compose.yml` starts Ollama first. A one-shot `ollama-model-init` service waits for
Ollama to become healthy, calls Ollama's `/api/pull` endpoint for `qwen3:8b`, verifies the
model appears in `/api/tags`, then exits successfully. The FastAPI backend starts after that
and sends chat requests to Ollama's `/api/chat` endpoint.

## Local Development

API:

```sh
python -m pip install -r api/requirements-dev.txt
PYTHONPATH=api pytest api/tests
```

Web:

```sh
cd web
npm install
npm run dev
```

## Configuration

The API reads:

- `OLLAMA_BASE_URL`, default `http://localhost:11434`
- `OLLAMA_MODEL`, default `qwen3:8b`
- `OLLAMA_THINK`, default `false`

The web app reads:

- `VITE_API_BASE_URL`, default `http://localhost:8000`

## GPU Notes

The Ollama service requests all available GPUs with Docker Compose's `gpus: all` setting.
On WSL2 with Docker Desktop, verify GPU visibility with:

```sh
nvidia-smi
docker info --format '{{json .Runtimes}}'
docker compose logs ollama | grep -E 'inference compute|offloaded'
```

Expected Ollama logs should mention `library=CUDA` and show model layers offloaded to GPU.
On the initial development machine, `qwen3:8b` used about 5.5 GiB total model memory and
offloaded `37/37` layers to an NVIDIA GeForce RTX 5070 Laptop GPU with 8 GiB VRAM.
