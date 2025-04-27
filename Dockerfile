# Dockerfile para dockerizar el cliente web de Memory Game

# Imagen base ligera con Python 3.10
FROM python:3.10-slim

# Directorio de trabajo
WORKDIR /app

# Copiar requisitos e instalar dependencias
# (Asume que tengas un requirements.txt con Flask, grpcio, protobuf)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código de la aplicación al contenedor
COPY . /app

# Variables de entorno: Flask y servidor gRPC
ENV FLASK_APP=client_web.py
ENV FLASK_RUN_HOST=0.0.0.0
# Por defecto conecta a localhost:50051, puede sobreescribirse con MEMORY_SERVER
ENV MEMORY_SERVER=localhost:50051

# Exponer el puerto 8081 para el cliente web
EXPOSE 8081

# Comando de arranque: lanzar Flask
CMD ["flask", "run", "--port=8081"]
