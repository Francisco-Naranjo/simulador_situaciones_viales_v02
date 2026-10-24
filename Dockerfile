# Dockerfile multi-etapa: compila el frontend React y sirve con FastAPI
# ---------------------------------------------------------------- etapa 1: frontend
FROM node:20-slim AS frontend-builder
WORKDIR /build
COPY frontend/package.json ./
RUN npm install --no-audit
COPY frontend/ ./
RUN npm run build

# ---------------------------------------------------------------- etapa 2: backend
FROM python:3.12-slim
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=frontend-builder /build/dist ./frontend/dist

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
