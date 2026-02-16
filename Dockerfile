# Stage 1: Build dashboard
FROM node:22-slim AS frontend
WORKDIR /app/dashboard
COPY dashboard/package.json dashboard/package-lock.json ./
RUN npm ci
COPY dashboard/ ./
RUN npm run build

# Stage 2: Python runtime
FROM python:3.13-slim
WORKDIR /app

# Copy Python source + metadata needed for install
COPY pyproject.toml README.md ./
COPY modelab/ modelab/
COPY server/ server/

# Install Python dependencies
RUN pip install --no-cache-dir ".[server]"

# Copy built dashboard
COPY --from=frontend /app/dashboard/dist dashboard/dist

EXPOSE 8100

CMD ["python", "-m", "uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8100"]
