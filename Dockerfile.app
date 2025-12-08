FROM python:3.8-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Force demo mode in container so external connections are disabled by default
ENV SAP_GATEWAY_DEMO=1

WORKDIR /app

# Sistem bağımlılıkları (gerekirse genişletilebilir)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    python3-dev \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Kütüphaneler
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip setuptools wheel
# Install Cython/wheel early to help build packages like lxml if needed
RUN pip install cython wheel
RUN pip install -r /app/requirements.txt

# Uygulama dosyalarını kopyala
COPY . /app

# Varsayılan Streamlit portu: 80 (Azure App Service için uygun)
ENV PORT=80

EXPOSE 80

# Basit entrypoint, env'den PORT'u alarak Streamlit'i başlatır
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh
# Ensure entrypoint has UNIX line endings so /bin/sh can execute it inside container
RUN sed -i 's/\r$//' /usr/local/bin/docker-entrypoint.sh || true

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

