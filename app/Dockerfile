FROM python:3.11-slim

# fonts-noto-core: Latin, Bengali (Assamese) and Devanagari glyphs for the PDF acknowledgment
RUN apt-get update && apt-get install -y --no-install-recommends fonts-noto-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /var/sewasetu/uploads /var/log/sewasetu

EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--worker-class", "gthread", "--threads", "8", "--timeout", "60", "app:app"]
