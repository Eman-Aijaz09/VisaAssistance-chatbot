# ---------- Application tier: FastAPI + RAG pipeline ----------
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/models

WORKDIR /app

# 1. CPU-only PyTorch (the default PyPI build includes GPU libraries and is several GB)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# 2. The rest of the API's Python packages
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

# 3. Download the embedding model at build time so containers start fast
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-base-en-v1.5')"
ENV HF_HUB_OFFLINE=1

# 4. Application code
COPY . .

# 5. Run as a non-root user
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000
CMD ["uvicorn", "fast_api:app", "--host", "0.0.0.0", "--port", "8000"]
