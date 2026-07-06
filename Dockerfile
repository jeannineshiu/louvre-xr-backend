FROM python:3.10-slim

WORKDIR /app

# System dependencies for OpenCV
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Railway injects PORT at runtime
ENV PORT=8000
EXPOSE $PORT

# --proxy-headers + --forwarded-allow-ips='*': Railway sits behind a proxy, so
# uvicorn must trust its X-Forwarded-For to see real client IPs (needed for
# per-IP rate limiting in server.py — otherwise every request looks the same).
CMD uvicorn server:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips='*'
