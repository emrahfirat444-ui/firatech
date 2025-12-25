import azure.functions as func
from datetime import datetime
import os
import sys

# Proje dizinini path'e ekle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/../..')

from app import scrape_turkish_ecommerce_sites

def main(mytimer: func.TimerRequest) -> None:
    """
    Azure Functions Timer Trigger - Her gün 03:00 UTC'de çalışır
    Türk e-ticaret sitelerini tarayarak Azure Table'a veri kaydeder
    """
    utc_timestamp = datetime.utcnow().isoformat()

    if mytimer.past_due:
        print('Timer tetiklemesi geçikmiş.')

    print(f'Timer trigger fonksiyonu çalıştı: {utc_timestamp}')
    print(f'Günlük e-ticaret taraması başlatılıyor...')

    # Safety guard: if STOP_COSTS=1 (default), skip execution to avoid incurring costs
    if os.getenv("STOP_COSTS", "1") == "1":
        print("STOP_COSTS=1 - skipping Azure Timer trigger to avoid cost incurrence.")
        return

    try:
        scrape_turkish_ecommerce_sites()
        print(f'[{utc_timestamp}] Tarama başarıyla tamamlandı ve Azure Table\'a kaydedildi.')
    except Exception as e:
        print(f'[{utc_timestamp}] Hata oluştu: {str(e)}')
