FROM python:3.12-slim

WORKDIR /app

# Install deps first for better layer caching.
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# App code, recipe data, and the static frontend.
COPY backend/app /app/app
COPY assets /app/assets
COPY frontend /app/frontend

# Container paths (overridable). DB lives in /data so it can be a mounted volume.
ENV RECIPES_PATH=/app/assets/recipes.json \
    FRONTEND_DIR=/app/frontend \
    PANTRYPAL_DB=/data/pantrypal.db \
    PYTHONUNBUFFERED=1

RUN mkdir -p /data
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
