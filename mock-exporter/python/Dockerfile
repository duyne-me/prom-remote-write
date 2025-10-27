# Simple Python mock exporter with uv
FROM python:3.11-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Set working directory
WORKDIR /app

# Copy application files
COPY main.py config.yml pyproject.toml ./

# Install dependencies directly
RUN uv pip install --system prometheus-client pyyaml fastapi uvicorn

# Expose port
EXPOSE 2112

# Run the application
CMD ["python", "main.py"]
