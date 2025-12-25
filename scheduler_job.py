"""
Günlük e-ticaret sitelerini tarayarak Azure Table'a kayıt eden scheduler job.
Bu script Azure Functions, cron job veya başka bir zamanlayıcı ile günlük çalıştırılabilir.
"""
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Safety guard: if STOP_COSTS=1 (default), exit to avoid incurring costs
if os.getenv("STOP_COSTS", "1") == "1":
    print("STOP_COSTS=1 - exiting to avoid cost incurrence.")
    raise SystemExit(0)

# Import scraping function from app.py
sys.path.insert(0, os.path.dirname(__file__))
from app import scrape_turkish_ecommerce_sites

def run_daily_scraping():
    """Günlük scraping job'u çalıştır"""
    print(f"[{datetime.now()}] Günlük e-ticaret taraması başlatılıyor...")
    
    try:
        scrape_turkish_ecommerce_sites()
        print(f"[{datetime.now()}] Tarama başarıyla tamamlandı ve Azure Table'a kaydedildi.")
    except Exception as e:
        print(f"[{datetime.now()}] Hata: {str(e)}")

if __name__ == "__main__":
    run_daily_scraping()
