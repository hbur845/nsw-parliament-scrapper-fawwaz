FROM docker.io/astral/uv:python3.12-bookworm-slim

# Prevent Python from writing .pyc files and use unbuffered stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install Python dependencies first for better build caching
COPY requirements.txt ./
RUN uv pip install --system -r requirements.txt

# Copy the rest of the application code
COPY . .

# Default storage location inside the container
RUN mkdir -p /app/storage

ENTRYPOINT ["python", "main.py"]
