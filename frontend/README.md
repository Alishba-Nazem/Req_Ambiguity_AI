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

To use the FastAPI backend, copy `.env.example` to `.env` and set `VITE_USE_MOCK=false`. Start the API on port 8000. Vite proxies `/api` during development.
