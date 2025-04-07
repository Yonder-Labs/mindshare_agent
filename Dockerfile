FROM --platform=linux/amd64 python:3.9.0-slim-buster

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libssl-dev \
    pkg-config \
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Setup virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --upgrade pip setuptools wheel

# Copy and install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/

# Create entrypoint script to installa nearai cli
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Phala config
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
RUN mkdir -p /var/run && chmod 777 /var/run
EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
CMD ["python", "-m", "src.scheduler.scheduler"]