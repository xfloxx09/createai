FROM python:3.12-slim AS backend-build

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    imagemagick \
    fonts-liberation \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN pip install --no-cache-dir --upgrade pip wheel
RUN pip install --no-cache-dir 'setuptools<70'
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --no-build-isolation openai-whisper==20240930
RUN pip install --no-cache-dir setuptools
RUN pip install --no-cache-dir -r requirements.txt && python -c "import asyncpg; print('asyncpg OK')"
COPY backend/ .

FROM node:20-alpine AS frontend-build
WORKDIR /app
COPY frontend/package.json ./
RUN npm install
COPY frontend/ .
RUN npm run build

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    imagemagick \
    fonts-liberation \
    libpq-dev \
    nginx \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip setuptools wheel uvicorn celery redis

COPY --from=backend-build /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=backend-build /app /backend
COPY --from=frontend-build /app/dist /frontend

COPY <<'EOF' /etc/nginx/conf.d/default.conf
server {
    listen 80;
    location / {
        root /frontend;
        index index.html;
        try_files $uri $uri/ /index.html;
    }
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF

ENV PYTHONPATH=/backend
CMD ["sh", "-c", "nginx && uvicorn app.main:app --host 127.0.0.1 --port 8000"]
