FROM python:3.10-slim

WORKDIR /app
COPY . /app

# Atualizar pacotes do sistema / instalar dependências básicas
RUN apt-get update && \
    apt-get install -y gcc libxml2-dev libxslt1-dev python3-dev && \
    pip install --no-cache-dir -r requirements.txt && \
    apt-get remove -y gcc python3-dev && \
    apt-get autoremove -y && \
    apt-get clean

CMD ["python", "server.py"]
