# Simple Python mock exporter with uv
FROM python:3.11-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Set working directory
WORKDIR /app

# Copy application files
COPY python/main.py python/config.yml python/pyproject.toml ./

# Install dependencies directly
RUN uv pip install --system prometheus-client pyyaml fastapi uvicorn

# Expose port
EXPOSE 2112

# Run the application
CMD ["python", "main.py"]
