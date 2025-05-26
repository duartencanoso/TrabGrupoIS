FROM python:3.10-slim

WORKDIR /app

# Instalar dependências pymongo e dnspython - precisar de build tools
RUN apt-get update && \
    apt-get install -y gcc build-essential libffi-dev && \
    rm -rf /var/lib/apt/lists/*

COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "app.py"]
