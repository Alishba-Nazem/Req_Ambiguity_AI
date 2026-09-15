---
title: Req Ambiguity AI
emoji: 🔍
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: "5.20.0"
app_file: app.py
pinned: false
---

# Requirement Ambiguity AI

Two-stage BERT requirement analysis. Stage A classifies clean vs ambiguous; Stage B assigns an ambiguity type. An optional LLM can add rewrite evidence. The React frontend is hosted separately (for example on Vercel) and is not served by this Space.

## Hugging Face ZeroGPU Space (free)

This is the **free** deployment path. Create a **Gradio** Space with **ZeroGPU** hardware. Do **not** choose Docker: Docker Spaces require a paid plan.

### 1. Create the Space

1. On Hugging Face, create a new Space.
2. SDK: **Gradio**.
3. Hardware: **ZeroGPU** (Space settings → Hardware). CPU Gradio hosting is not assumed on the free account.
4. Keep the Space **public** so the Vercel app can call it without an HF token in the browser.
5. Push this repository (or the Space files) so the root contains `app.py`, `backend/`, `ml/config.py`, and `requirements.txt`.

Do not add a new Dockerfile for this Space. The existing `Dockerfile` is only for a future paid Docker Space.

### 2. Upload inference files only

Upload **only** the two trained inference folders. Do **not** upload `dataset/`, training scripts, `checkpoint-*`, `optimizer.pt`, or other optimizer/log files.

```text
ml/outputs_two_stage/stage_a/best_model/
    config.json
    tokenizer.json
    tokenizer_config.json
    model.safetensors

ml/outputs_two_stage/stage_b/best_model/
    config.json
    tokenizer.json
    tokenizer_config.json
    model.safetensors
```

`model.safetensors` is large; use Git LFS. The Space must be able to load both stages from those paths (`MODEL_DIR` defaults to `ml/outputs_two_stage`).

### 3. Space secrets (backend only)

| Name | Secret? | Example |
| --- | --- | --- |
| `MODEL_DIR` | no | `ml/outputs_two_stage` |
| `LLM_ENABLED` | no | `true` only if you want Gemini/OpenAI evidence |
| `LLM_PROVIDER` | no | `gemini` |
| `LLM_MODEL` | no | `gemini-2.0-flash` |
| `LLM_BASE_URL` | no | `https://generativelanguage.googleapis.com/v1beta` |
| `LLM_API_KEY` | **yes** | Space secret. Never put this in a `VITE_*` frontend variable. |

Full placement notes: [docs/huggingface-space.md](docs/huggingface-space.md).

### 4. Gradio API the Vercel frontend should call

Named endpoints (Gradio `api_name`). Prefix with `/` when using `@gradio/client`.

| Function | `api_name` | GPU? | Inputs | Output |
| --- | --- | --- | --- | --- |
| `health` | `/health` | no | none | `HealthResponse` JSON |
| `analyze` | `/analyze` | yes (`@spaces.GPU`) | `requirement: str` | `AnalyzeResponse` JSON (same as FastAPI `POST /api/analyze`) |
| `generate_requirement` | `/generate_requirement` | yes (`@spaces.GPU`) | `idea: str`, `requirement_type: str` (`auto` or a kind), `details: str` | `GenerateResponse` JSON (same as FastAPI `POST /api/generate-requirement`) |

Errors are returned in the JSON body as `{ "error": "...", "code": "validation_error" | "model_unavailable" }` because Gradio does not use FastAPI status codes.

## Local FastAPI (unchanged)

```text
python -m pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

- `GET /api/health`
- `POST /api/analyze`
- `POST /api/generate-requirement`
