# Dockerfile — ArthAI Production Container
FROM python:3.11-slim

# System dependencies
RUN apt-get update && apt-get install -y \
    gcc g++ libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 arthaai
WORKDIR /app

# Install Python deps first (cache layer)
COPY requirements.txt requirements-dashboard.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -r requirements-dashboard.txt

# Copy source
COPY --chown=arthaai:arthaai . .

# Create runtime dirs
RUN mkdir -p /app/logs /app/data_store \
    && chown -R arthaai:arthaai /app

USER arthaai

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

EXPOSE 8501

CMD ["streamlit", "run", "dashboard/app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]
