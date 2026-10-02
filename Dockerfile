# Painel Oriximiná em um container (Docker Desktop)
# Montar e abrir:  docker compose up -d --build   →   http://localhost:8501
# 3.13: todas as bibliotecas (shapely, geopandas...) já vêm prontas para ele, sem compilar nada
FROM python:3.13-slim

# Hora do Brasil (datas dos problemas reportados, "Próxima atualização"...) e Python sem buffer nos logs
ENV TZ=America/Santarem \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Bibliotecas primeiro: só são instaladas de novo quando o requirements.txt muda
COPY requirements.txt .
# Mais paciência com a internet: espera mais e tenta de novo se a conexão cair
RUN pip install --default-timeout=120 --retries 10 -r requirements.txt

# O código do painel e os dados que vêm junto (as pastas que o painel altera ficam ligadas
# à pasta do computador no docker-compose.yml, para não se perderem ao recriar o container)
COPY . .

EXPOSE 8501

# Avisa o Docker Desktop se o painel parou de responder
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"

CMD ["python", "-m", "streamlit", "run", "painel.py", \
     "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
