FROM python:3.10-slim

# install OS deps for rembg (libomp & libgl for onnxruntime)
RUN apt-get update && \
    apt-get install -y libomp5 libgl1 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8080
CMD ["gunicorn", "-b", ":8080", "app:app", "--timeout", "120", "--workers", "1"]
