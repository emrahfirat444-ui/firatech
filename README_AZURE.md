**Azure App Service (Container) için Docker & Deploy Rehberi**

Bu dosya, `app.py` (Streamlit UI) ve `sap_gateway.py` (Flask gateway) için Dockerfile, docker-compose ve Azure'a nasıl deploy edileceğine dair adımları içerir.

Özet adımlar
1. Local olarak Docker imajlarını test edin (`docker-compose up --build`).
2. Azure Container Registry (ACR) oluşturun ve imajları buraya push edin.
3. Azure App Service (Linux) veya App Service with Docker Compose kullanarak imajları çalıştırın.

1) Yerel test

- Docker Compose ile (lokal):
```powershell
docker-compose build
docker-compose up
```

Uygulama şu adreslerde erişilebilir olur:
- Streamlit UI: `http://localhost:8501`
- Gateway (demo): `http://localhost:5000`

2) Azure Container Registry oluşturma

Azure CLI ile örnek:
```powershell
az group create --name myResourceGroup --location northeurope
az acr create --resource-group myResourceGroup --name myYatasACR --sku Basic
az acr login --name myYatasACR
```

3) İmajları etiketleme ve push etme

Streamlit app:
```powershell
docker build -f Dockerfile.app -t myyatasacr.azurecr.io/yatas-streamlit:latest .
docker push myyatasacr.azurecr.io/yatas-streamlit:latest
```

Gateway (opsiyonel, demo modda da çalışır):
```powershell
docker build -f Dockerfile.gateway -t myyatasacr.azurecr.io/yatas-gateway:latest .
docker push myyatasacr.azurecr.io/yatas-gateway:latest
```

4) Azure App Service (tek container) — Streamlit

Azure Portal'da ya da CLI ile yeni App Service (Linux) oluşturun ve "Docker Container" seçeneğini kullanın. Image olarak `myyatasacr.azurecr.io/yatas-streamlit:latest` gösterin. App Service, container içindeki portu 80 olarak bekleyebilir; bu nedenle container içinde Streamlit'i 8501 portunda çalıştırırken App Service ayarlarında "Startup Command" kullanarak `streamlit run app.py --server.port 80 --server.address 0.0.0.0` kullanabilirsiniz.

Alternatif: App Service (Multi-container) / Docker Compose
- Eğer hem `app` hem `gateway`'i tek App Service üzerinde çalıştırmak isterseniz, App Service > Deployment Center > Docker Compose seçeneği ile `docker-compose.yml` kullanabilirsiniz. Azure, compose içindeki servisleri başlatacaktır.

5) Ortam değişkenleri

Azure Portal üzerinden App Service > Configuration sekmesinden gerekli env değişkenlerini ekleyin (SAP_HOST, SAP_CLIENT, SAP_PASSWORD, SAP_GATEWAY_DEMO, NWRFCSDK_HOME vb.).

Güvenlik notu
- SAP bilgilerini ACR veya repo'ya koymayın; App Service Configuration (Application Settings) veya Key Vault ile saklayın.
- Üretimde gateway'i internete açık bırakmayın; gateway sadece app'in erişebileceği şekilde iç ağa alın veya ayrı App Service içinde IP kısıtlaması uygulayın.

Ek kaynaklar
- https://learn.microsoft.com/en-us/azure/app-service/quickstart-custom-container
- https://learn.microsoft.com/en-us/azure/container-registry/
