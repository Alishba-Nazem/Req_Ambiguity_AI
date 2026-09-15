# Requirement Ambiguity AI — frontend

Vite + React + TypeScript + Tailwind. Mock analysis is on by default so the UI can be used without the BERT API.

```text
cd frontend
npm install
npm run dev
```

Opens at http://localhost:3000

```text
npm run build
```

## Backends

| Mode | Env | Used for |
| --- | --- | --- |
| Mock | `VITE_USE_MOCK=true` (default) | UI demos without a backend |
| Local FastAPI | `VITE_USE_MOCK=false` | Dev with Vite proxy `/api` → port 8000 |
| Vercel production | `VITE_USE_MOCK=false` + server `HF_TOKEN` | Same-origin `/api/*` serverless proxy → Hugging Face Space |

Never put `HF_TOKEN`, `LLM_API_KEY`, or other secrets in `VITE_*` variables.

### Vercel serverless proxy

- `POST /api/analyze` → Space `/analyze` (authenticated with `HF_TOKEN`)
- `POST /api/generate-requirement` → Space `/generate_requirement`

Server env vars: `HF_TOKEN` (required), `HF_SPACE` (defaults to `lishyyyy-710/req-ambiguity-ai`).

Copy `.env.example` to `.env` for local overrides.
