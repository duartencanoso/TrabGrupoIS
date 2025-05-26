FROM python:3.10-slim

# Diretório trabalho
WORKDIR /app

# Copiar todos os ficheiros
COPY . /app

# Instalar dependências do sistema e Python
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Comando de arranque
CMD ["python", "server.py"]
