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
| Local FastAPI | `VITE_USE_MOCK=false` and empty `VITE_HF_SPACE` | Dev with Vite proxy `/api` → port 8000 |
| Hugging Face Gradio | `VITE_USE_MOCK=false` and `VITE_HF_SPACE=lishyyyy-710/req-ambiguity-ai` | Vercel production |

Never put `LLM_API_KEY` or other secrets in `VITE_*` variables. The Space keeps secrets server-side.

Copy `.env.example` to `.env` for local overrides.
