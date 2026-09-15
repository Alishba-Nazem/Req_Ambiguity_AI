FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=7860 \
    MODEL_DIR=ml/outputs_two_stage \
    FRONTEND_URL=http://localhost:3000

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir torch==2.14.0 --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/
COPY ml/__init__.py ml/config.py ml/

RUN mkdir -p \
    ml/outputs_two_stage/stage_a/best_model \
    ml/outputs_two_stage/stage_b/best_model

COPY ml/outputs_two_stage/stage_a/best_model/ ml/outputs_two_stage/stage_a/best_model/
COPY ml/outputs_two_stage/stage_b/best_model/ ml/outputs_two_stage/stage_b/best_model/

EXPOSE 7860

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
