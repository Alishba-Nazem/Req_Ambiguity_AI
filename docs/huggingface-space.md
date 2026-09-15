# Hugging Face Space

Free hosting uses a **Gradio ZeroGPU** Space (`app.py`). The FastAPI app (`backend.main:app`) stays for local development. The existing `Dockerfile` is kept for a future **paid** Docker Space; do not use Docker on the free Hugging Face plan.

The Space does not train models and does not serve the React frontend.

## Inference folders only

Do **not** upload `dataset/`, training scripts, `checkpoint-*` directories, `optimizer.pt`, logs, or `*.pth` files.

Copy **only** these two folders onto the Space so they sit next to `backend/` and `ml/`:

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

`MODEL_DIR` defaults to `ml/outputs_two_stage`. The runtime then loads:

- Stage A: `$MODEL_DIR/stage_a/best_model`
- Stage B: `$MODEL_DIR/stage_b/best_model`

If you set `MODEL_DIR` to another path, keep that same `stage_a/best_model` and `stage_b/best_model` layout under it.

## Create a free ZeroGPU Space

1. Hugging Face → New Space.
2. SDK: **Gradio** (`sdk: gradio`, `app_file: app.py` in the root README).
3. Hardware: **ZeroGPU**. Do not pick a paid GPU or Docker.
4. Visibility: **public** so Vercel can call the Gradio API without putting an HF token in `VITE_*` variables.
5. Upload the repository files, then upload the two `best_model` folders (Git LFS for `model.safetensors`).
6. Settings → Secrets: `LLM_API_KEY` only if you enable the LLM. Never expose that key to the frontend.

ZeroGPU has **no real GPU at import time**. Both BERT stages are loaded once in `app.py` (after `import spaces`) so ZeroGPU can pack the CUDA placements. `@spaces.GPU` is used only on `analyze` and `generate_requirement`. `health` stays on CPU.

Local FastAPI is unchanged:

```text
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

To try the Gradio app locally (optional):

```text
python -m pip install -r requirements.txt
python -m pip install spaces
python app.py
```

## Environment variables

| Name | Secret? | Example |
| --- | --- | --- |
| `MODEL_DIR` | no | `ml/outputs_two_stage` |
| `LLM_ENABLED` | no | `true` only if you want Gemini/OpenAI evidence |
| `LLM_PROVIDER` | no | `gemini` |
| `LLM_MODEL` | no | `gemini-2.0-flash` |
| `LLM_BASE_URL` | no | `https://generativelanguage.googleapis.com/v1beta` |
| `LLM_API_KEY` | **yes** | Space secret only. Never a `VITE_*` variable. |

`FRONTEND_URL` is used by FastAPI CORS for local/Docker hosting. The Gradio Space API does not require it.

## Check that both stages loaded

Call Gradio `/health` (or FastAPI `GET /api/health` locally). You want:

```json
{
  "status": "ok",
  "model_loaded": true,
  "stage_a_loaded": true,
  "stage_b_loaded": true,
  "error": null
}
```

If a `best_model` folder is missing `model.safetensors`, `model_loaded` is false and `error` names Stage A and/or Stage B.

## Gradio API (Vercel)

Base URL: `https://<user>-<space>.hf.space`

| `api_name` | Inputs (positional) | Success output | Failure output |
| --- | --- | --- | --- |
| `/health` | none | `HealthResponse` | n/a |
| `/analyze` | `requirement: string` | `AnalyzeResponse` (same fields as `POST /api/analyze`) | `{ "error": string, "code": "validation_error" \| "model_unavailable" }` |
| `/generate_requirement` | `idea: string`, `requirement_type: string` (`auto` or a kind), `details: string` | `GenerateResponse` (same fields as `POST /api/generate-requirement`, including nested `analysis`) | `{ "error": string, "code": "validation_error" \| "model_unavailable" }` |

`requirement_type` kinds: `functional`, `performance`, `security`, `usability`, `availability`, `compatibility`, `other`. Pass `"auto"` to let the backend infer the kind.

Use `@gradio/client` `Client.connect("<user>/<space>").predict("/analyze", { requirement })`. The first output in `result.data` is the JSON object. Check `payload.error` because Gradio calls are HTTP 200 even on validation/model errors.

Local FastAPI routes are unchanged:

- `GET /api/health`
- `POST /api/analyze`
- `POST /api/generate-requirement`

## Paid Docker Space (optional, later)

`Dockerfile` and `.dockerignore` remain in the repo. They run FastAPI with uvicorn. That path needs a paid Hugging Face Docker plan and is not used for the free ZeroGPU deployment.
