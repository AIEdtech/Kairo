FROM python:3.11-slim

# Install ffmpeg for Edge TTS audio decoding
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

EXPOSE ${PORT:-8000}

CMD uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}
