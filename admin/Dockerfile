FROM node:22-alpine AS frontend-build
WORKDIR /frontend
COPY admin/frontend/package.json admin/frontend/package-lock.json ./
RUN npm ci
COPY admin/frontend/index.html admin/frontend/tsconfig.json admin/frontend/vite.config.ts ./
COPY admin/frontend/src ./src
RUN npm run build

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends openssh-client wireguard-tools qrencode && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY admin/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY admin/backend /app/admin/backend
COPY admin/backend/__init__.py /app/admin/__init__.py
COPY --from=frontend-build /frontend/dist /app/admin/frontend/dist
ENV PYTHONPATH=/app
CMD ["uvicorn","admin.backend.app:app","--host","0.0.0.0","--port","8000","--proxy-headers","--forwarded-allow-ips=*"]
