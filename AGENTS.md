# Repository Guidelines

## Project Structure & Module Organization

This repo contains a local LLM web app scaffold.

- `api/`: Python FastAPI backend. App code lives in `api/app/`; tests live in `api/tests/`.
- `web/`: React + Vite + TypeScript frontend. Source code lives in `web/src/`.
- `docker-compose.yml`: Local stack for Ollama, model initialization, API, web, and Dozzle.
- `.github/workflows/`: CI and release automation.
- `.github/dependabot.yml`: Dependency update configuration.

## Build, Test, and Development Commands

- `docker compose up --build`: Build and run the full local stack.
- `docker compose config`: Validate Compose syntax and resolved configuration.
- `docker compose logs -f ollama`: Follow Ollama logs, including GPU detection and model loading.
- `PYTHONPATH=api pytest api/tests`: Run backend tests.
- `cd web && npm ci`: Install frontend dependencies from the lockfile.
- `cd web && npm run build`: Type-check and build the frontend.

Use `http://localhost:5173` for the web app, `http://localhost:8000/health` for API health, and `http://localhost:9999` for Dozzle logs.

## Coding Style & Naming Conventions

Keep changes small and explicit. Use 2-space indentation for TypeScript, CSS, JSON, and YAML. Use 4-space indentation for Python.

Python modules should use `snake_case`; React components should use `PascalCase`; local variables and functions in TypeScript should use `camelCase`. Keep API request/response models typed with Pydantic and frontend API shapes typed in TypeScript.

No formatter is currently configured. Preserve existing style and run the relevant build/tests before committing.

## Testing Guidelines

Backend tests use `pytest` and should be named `test_*.py` under `api/tests/`. Prefer mocked Ollama calls for unit tests so CI does not need a model download or GPU.

Frontend validation currently relies on `npm run build`, which runs TypeScript checking and Vite build. Add focused tests before introducing complex UI logic.

## Commit & Pull Request Guidelines

Use Conventional Commits, for example:

- `feat: add local LLM web app`
- `fix: handle Ollama startup failures`
- `chore: update CI dependencies`

PRs should include a concise summary, validation steps, and any local runtime notes. For UI changes, include screenshots when practical. Keep PR titles aligned with the main commit title when the branch has one primary change.

## Security & Configuration Tips

Do not commit `.env` files, secrets, model blobs, or generated dependency folders. Ollama models are stored in the Docker volume `ollama-data`. For WSL2/NVIDIA GPU troubleshooting, check `nvidia-smi` and confirm Ollama logs mention `library=CUDA` and layer offload.
