FROM python:3.8-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Sistem bağımlılıkları (gerekirse genişletilebilir)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Kütüphaneler
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip setuptools wheel
RUN pip install -r /app/requirements.txt

# Uygulama dosyalarını kopyala
COPY . /app

# Varsayılan Streamlit portu: 80 (Azure App Service için uygun)
ENV PORT=80

EXPOSE 80

# Basit entrypoint, env'den PORT'u alarak Streamlit'i başlatır
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

