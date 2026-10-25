# Production Dockerfile for Sovereign 3D Simulator
FROM python:3.12-slim
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HOST=0.0.0.0
ENV PORT=8000

# Install backend dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code, launcher, and precompiled production frontend distribution
COPY backend/ ./backend/
COPY run.py .
COPY frontend/dist ./frontend/dist

# Expose HTTP & WebSocket port
EXPOSE 8000

# Launch kingdom cluster
CMD ["python", "run.py", "--host", "0.0.0.0", "--no-browser"]
