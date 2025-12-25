"""
Background scheduler - Günde 1 kez e-ticaret sitelerini tarayan job
APScheduler kullanarak container'da çalışır
"""
import os
import sys
from datetime import datetime
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler

# Load environment
load_dotenv()

# Safety guard: if STOP_COSTS=1 (default), exit to avoid incurring costs
if os.getenv("STOP_COSTS", "1") == "1":
    print("STOP_COSTS=1 - exiting to avoid cost incurrence.")
    sys.exit(0)

# Import scraping function from app.py
sys.path.insert(0, os.path.dirname(__file__))
from app import scrape_turkish_ecommerce_sites

def scheduled_scraping_job():
    """Zamanlanmış scraping job'u"""
    print(f"[{datetime.now()}] ⏰ Günlük e-ticaret taraması başlatılıyor...")
    try:
        scrape_turkish_ecommerce_sites()
        print(f"[{datetime.now()}] ✅ Tarama başarıyla tamamlandı ve Azure Table'a kaydedildi.")
    except Exception as e:
        print(f"[{datetime.now()}] ❌ Hata: {str(e)}")

def start_background_scheduler():
    """
    Background'da scheduler'ı başlat
    Her gün 03:00 UTC'de çalışır
    """
    scheduler = BackgroundScheduler()
    
    # Günlük job: Her gün 03:00 UTC'de çalış
    scheduler.add_job(
        scheduled_scraping_job,
        'cron',
        hour=3,
        minute=0,
        name='daily_ecommerce_scraping',
        id='daily_scraper'
    )
    
    scheduler.start()
    print(f"[{datetime.now()}] 🚀 Background scheduler başlatıldı. Her gün 03:00 UTC'de çalışır.")
    
    # Scheduler'ı canlı tut
    try:
        while True:
            pass
    except KeyboardInterrupt:
        scheduler.shutdown()
        print("Scheduler kapatıldı.")

if __name__ == "__main__":
    start_background_scheduler()
