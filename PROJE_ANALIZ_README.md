# Proje Analiz Özelliği Dokümantasyonu

## Genel Bakış

Streamlit uygulamasına **Proje Analiz** sayfası eklendi. Bu sayfa:
- Türkiye'deki e-ticaret sitelerinden (Trendyol, Hepsiburada, N11) günlük olarak en çok satan ürünleri toplar
- Verileri Azure Table Storage'a kaydeder
- Her giriş yaptığınızda top 10 ürünü gösterir
- Web scraping agent'ları ile otomatik veri toplama yapar

## Mimari

### 1. Frontend (Streamlit)
- Menu sayfasında yeni **"📈 PROJE ANALİZ"** butonu
- `proje_analiz` sayfası: Top 10 ürün tablosu, grafik ve görsel galeri
- Manuel yenileme butonu

### 2. Backend (Python)
- `fetch_top_products_from_azure()`: Azure Table'dan günlük verileri çeker
- `scrape_turkish_ecommerce_sites()`: E-ticaret sitelerini tarayarak ürün bilgilerini toplar

### 3. Azure Table Storage
- Table Name: `TopProductsDaily` (configurable)
- PartitionKey: Tarih (YYYYMMDD formatında, örn: 20251210)
- RowKey: UUID
- Columns: Rank, ProductName, Price, Category, ImageUrl, Source, Url

### 4. Scheduler Job
- `scheduler_job.py`: Günlük çalıştırılacak script
- APScheduler ile veya Azure Functions ile zamanlanabilir

## Kurulum

### Gerekli Environment Variables

`.env` dosyasına ekleyin:

```bash
# Azure Table Storage
AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=<account_name>;AccountKey=<account_key>;EndpointSuffix=core.windows.net"
AZURE_TABLE_NAME="TopProductsDaily"

# Demo mode (0 yaparak gerçek scraping'i aktifleştirin)
SAP_GATEWAY_DEMO=1
```

### Paket Kurulumu

```bash
pip install azure-data-tables==12.4.0 APScheduler==3.10.4
```

### Azure Table Storage Oluşturma

```bash
# Azure CLI ile
az storage account create --name yatasanalysis --resource-group firatech-rg --location northeurope --sku Standard_LRS

# Connection string'i alın
az storage account show-connection-string --name yatasanalysis --resource-group firatech-rg
```

## Kullanım

### Manuel Test

```bash
# Günlük scraping job'u manuel çalıştırma
python scheduler_job.py
```

### Günlük Zamanlama

#### Option 1: APScheduler (container içinde)
`app.py`'ye ekleyin:

```python
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()
scheduler.add_job(scrape_turkish_ecommerce_sites, 'cron', hour=3, minute=0)  # Her gün 03:00'da
scheduler.start()
```

#### Option 2: Cron Job (Linux server)
```bash
crontab -e
# Her gün 03:00'da çalıştır
0 3 * * * cd /app && python scheduler_job.py >> /var/log/scraper.log 2>&1
```

#### Option 3: Azure Functions (Timer Trigger)
- Azure Portal'da Timer Trigger Function oluşturun
- Schedule: `0 0 3 * * *` (her gün 03:00)
- Function code'a `scrape_turkish_ecommerce_sites()` fonksiyonunu çağırın

## Demo Mode

`DEMO_MODE=True` iken (varsayılan):
- Gerçek web scraping çalışmaz
- Placeholder demo data gösterilir
- Azure bağlantısı yapılmaz

Production'da `SAP_GATEWAY_DEMO=0` yaparak gerçek scraping'i aktifleştirin.

## Web Scraping Detayları

### Desteklenen Siteler
1. **Trendyol**: `https://www.trendyol.com/cok-satanlar`
2. **Hepsiburada**: `https://www.hepsiburada.com/cok-satanlar`
3. **N11**: `https://www.n11.com/cok-satanlar`

### Toplanan Veriler
- Ürün adı
- Fiyat (TL)
- Kategori
- Görsel URL
- Ürün URL
- Kaynak site

### Rate Limiting & Best Practices
- User-Agent header kullanılıyor
- Timeout: 10 saniye
- Her site için try-catch ile hata yönetimi
- İlk 10 ürün alınıyor

## Güvenlik Notları

1. **Connection String**: Production'da Azure Key Vault kullanın
2. **Rate Limiting**: Çok sık scraping yapmayın (günlük 1 kez yeterli)
3. **User-Agent**: Robotlar için uygun User-Agent kullanın
4. **robots.txt**: Sitelerin robots.txt kurallarına uyun

## Troubleshooting

### Azure Table bağlantı hatası
```
Error: Azure Table'dan veri çekerken hata
```
**Çözüm**: `AZURE_STORAGE_CONNECTION_STRING` doğru mu kontrol edin.

### Scraping timeout
```
requests.exceptions.Timeout
```
**Çözüm**: Timeout süresini artırın veya site URL'lerini kontrol edin.

### Selector bulunamadı
```
No products found
```
**Çözüm**: Siteler HTML yapısını değiştirmiş olabilir. Selector'ları güncelleyin.

## Gelecek Geliştirmeler

- [ ] Daha fazla e-ticaret sitesi ekle (GittiGidiyor, Çiçeksepeti, vb.)
- [ ] Kategori bazlı filtreleme
- [ ] Fiyat trend analizi (geçmiş 30 gün)
- [ ] Email bildirimleri (fiyat düştüğünde)
- [ ] Cache mekanizması (Redis)
- [ ] Asenkron scraping (asyncio, aiohttp)

## İletişim

Sorularınız için: emrahfirat@yatas.com

{
  "id": "local_test_user",
  "email": "test@yatas.com",
  "name": "Test Kullanıcı",
  "department": "IT",
  "position": "Uzman",
  "personnel_number": "00001234"
}
