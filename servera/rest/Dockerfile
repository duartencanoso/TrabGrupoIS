FROM python:3.10-slim

# Evita perguntas interativas durante instalação
ENV DEBIAN_FRONTEND=noninteractive

# Define diretório de trabalho
WORKDIR /app

# Copia todos os ficheiros para o container
COPY . /app

# Instala as dependências
RUN pip install --no-cache-dir -r requirements.txt

# Expõe a porta 5000 (Flask)
EXPOSE 5000

# Comando de arranque
CMD ["python", "app.py"]
