# BRT Fleet Movement Pipeline — Container image
# Runs: python run.py <RUN_ID> --auto
# Built for: Azure Container Apps Job (scheduled CRON trigger)

FROM python:3.13-slim

# System deps for openpyxl/pandas + Azure SDK
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libssl-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer cached unless requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Env vars are injected at Container Apps Job runtime (not baked in)
# Set UTF-8 to handle Unicode in logs (required on Linux too)
ENV PYTHONUTF8=1
ENV PYTHONUNBUFFERED=1

# Default entrypoint — RUN_ID is passed as a Container Apps Job argument
# e.g.  args: ["BRT-2026-06-17", "--auto"]
ENTRYPOINT ["python", "run.py"]
CMD ["--help"]
