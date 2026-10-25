# Multi-stage Dockerfile for Sovereign 3D Simulator
# Stage 1: Build React Three Fiber production bundle
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Production Python Runtime
FROM python:3.12-slim
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HOST=0.0.0.0
ENV PORT=8000

# Install backend dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and built frontend
COPY backend/ ./backend/
COPY run.py .
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Expose HTTP & WebSocket port
EXPOSE 8000

# Launch kingdom cluster
CMD ["python", "run.py", "--host", "0.0.0.0", "--port", "8000", "--no-browser"]
