import streamlit as st
import os
import requests
import json
from datetime import datetime, timedelta
import pandas as pd
import uuid

# Sayfa yapılandırması
st.set_page_config(page_title="Yataş Giriş", layout="wide")

# (Header removed) Top banner/logo and big title intentionally omitted from UI per request.

# Load configuration from environment to avoid embedding secrets in code
SSO_CONFIG = {
    "sso_url": os.getenv("SSO_URL", ""),
    "client_id": os.getenv("SSO_CLIENT_ID", "yatas_app_2025"),
    "client_secret": os.getenv("SSO_CLIENT_SECRET", ""),
    "redirect_uri": os.getenv("SSO_REDIRECT_URI", "http://localhost:8501")
}

# SAP RFC Konfigürasyonu (read from env; keep empty by default for demo)
SAP_CONFIG = {
    "host": os.getenv("SAP_HOST", ""),
    "client": os.getenv("SAP_CLIENT", ""),
    "sysnr": os.getenv("SAP_SYSNR", ""),
    "user": os.getenv("SAP_USER", ""),
    "password": os.getenv("SAP_PASSWORD", ""),
    "lang": os.getenv("SAP_LANG", "TR"),
    "group": os.getenv("SAP_GROUP", "YATAS")
}

# SAP REST API Gateway Konfigürasyonu
SAP_API_CONFIG = {
    "base_url": os.getenv("SAP_API_BASE_URL", os.getenv("SAP_GATEWAY_URL", "http://localhost:5000/api"))
}

# Demo mode flag - if set, short-circuit all external calls and use demo data
DEMO_MODE = os.getenv("SAP_GATEWAY_DEMO", "1").lower() in ("1", "true", "yes")
if DEMO_MODE:
    # Clear any external endpoints to avoid accidental network calls
    SSO_CONFIG["sso_url"] = ""
    SAP_API_CONFIG["base_url"] = ""

# CSS stilleri
st.markdown("""
    <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    
    /* Hide Streamlit elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display: none;}
    .stDecoration {display: none;}
    .stApp {background: #f5f5f5 !important;}
    .stAppViewContainer {padding: 0 !important;}
    [data-testid="stAppViewContainer"] {padding: 0 !important;}
    
    /* Responsive Login Container - simplified and pinned near top */
    .login-wrapper {
        position: fixed;
        top: 20px;
        left: 0;
        right: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 12px;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        margin: 0 auto;
        width: 100%;
        z-index: 9999;
    }
    .login-container {
        width: 100%;
        max-width: 420px;
        background: white;
        border-radius: 16px;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
        padding: 28px 22px;
        animation: slideIn 0.4s ease-out;
    }
    
    @keyframes slideIn {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .logo-container {
        text-align: center;
        margin-bottom: 40px;
    }
    
    .firatech-logo {
        width: 80px;
        height: 80px;
        margin: 0 auto 20px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 40px;
        font-weight: bold;
        color: white;
        box-shadow: 0 10px 30px rgba(102, 126, 234, 0.4);
    }
    
    .logo-text {
        font-size: 28px;
        font-weight: 700;
        color: #333;
        margin: 0;
        letter-spacing: -0.5px;
    }
    
    .logo-subtitle {
        font-size: 13px;
        color: #999;
        font-weight: 500;
        margin-top: 5px;
        letter-spacing: 0.5px;
    }
    
    .form-title {
        color: #333;
        text-align: center;
        font-size: 20px;
        font-weight: 600;
        margin-bottom: 30px;
        margin-top: 10px;
    }
    
    /* Form styling */
    .form-group {
        margin-bottom: 18px;
    }
    
    .form-label {
        display: block;
        font-size: 13px;
        font-weight: 600;
        color: #555;
        margin-bottom: 8px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .stApp .stTextInput input {
        background: #f5f5f5 !important;
        color: #333 !important;
        border: 2px solid #e0e0e0 !important;
        border-radius: 10px !important;
        padding: 12px 14px !important;
        font-size: 14px !important;
        transition: all 0.3s ease !important;
    }
    
    .stApp .stTextInput input:focus {
        background: #ffffff !important;
        border-color: #667eea !important;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1) !important;
    }
    
    /* Button styling */
    .stApp .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        color: white !important;
        border: none !important;
        padding: 12px 20px !important;
        font-size: 15px !important;
        font-weight: 600 !important;
        border-radius: 10px !important;
        width: 100% !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 8px 20px rgba(102, 126, 234, 0.3) !important;
        margin-top: 8px !important;
    }
    
    .stApp .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 12px 30px rgba(102, 126, 234, 0.4) !important;
    }
    
    .stApp .stButton > button:active {
        transform: translateY(0) !important;
    }
    
    /* Mobile responsive */
    @media (max-width: 480px) {
        .login-container {
            padding: 30px 20px;
            border-radius: 12px;
        }
        
        .logo-text {
            font-size: 24px;
        }
        
        .form-title {
            font-size: 18px;
            margin-bottom: 24px;
        }
        
        .firatech-logo {
            width: 70px;
            height: 70px;
            font-size: 36px;
        }
    }
    .leave-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 30px;
        border-radius: 10px;
        color: white;
        text-align: center;
        box-shadow: 0 10px 25px rgba(0,0,0,0.2);
    }
    .leave-number {
        font-size: 48px;
        font-weight: bold;
        margin: 20px 0;
    }
    .leave-label {
        font-size: 18px;
        opacity: 0.9;
    }
    .chat-message {
        padding: 15px 20px;
        border-radius: 12px;
        margin: 10px 0;
        word-wrap: break-word;
        line-height: 1.5;
    }
    .chat-user {
        background-color: #667eea;
        color: white;
        text-align: right;
        border-radius: 12px;
        margin-left: 40px;
        box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
    }
    .chat-ai {
        background-color: #f0f0f0;
        color: #333;
        border-left: 4px solid #764ba2;
        margin-right: 40px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    .chat-response-title {
        color: #667eea;
        font-weight: bold;
        margin-top: 10px;
        margin-bottom: 5px;
    }
    .chat-response-item {
        color: #333;
        margin: 5px 0;
        padding-left: 10px;
    }
    /* Dark theme inputs & buttons */
    .stApp input, .stApp textarea, .stApp select {
        background: #252631 !important;
        color: #e6e6e6 !important;
        border-radius: 10px !important;
        padding: 10px !important;
        border: 1px solid rgba(255,255,255,0.06) !important;
    }
    .stApp .stButton>button {
        background: linear-gradient(90deg,#2b2e3a,#3b3f4d) !important;
        color: #fff !important;
        border: 1px solid rgba(255,255,255,0.06) !important;
        padding: 8px 14px !important;
        border-radius: 10px !important;
        box-shadow: none !important;
    }
    .stApp .stButton>button:active { transform: translateY(1px); }
    /* Card like sections */
    .card-section {
        background: #0f1113;
        border: 1px solid rgba(255,255,255,0.03);
        padding: 18px;
        border-radius: 12px;
        margin-bottom: 18px;
    }
    .card-title { color: #e6e6e6; font-weight:600; margin-bottom:12px }
    /* Thumbnails and gallery */
    .thumb-img { width:100%; height:160px; object-fit:cover; border-radius:10px; border:1px solid rgba(255,255,255,0.04); }
    .thumb-wrap { padding:6px; background: #0b0c0e; border-radius:10px; }
    .preview-img { width:100%; max-width:760px; height:auto; border-radius:12px; border:1px solid rgba(255,255,255,0.04); }
    .small-muted { color: #9aa0a6; font-size:13px }
    /* Hover overlay and compact grid */
    .thumb-wrap { position: relative; overflow: hidden; }
    .thumb-wrap img.thumb-img { transition: transform 0.25s ease, filter 0.25s ease; display:block; }
    .thumb-wrap:hover img.thumb-img { transform: scale(1.06); filter: brightness(0.94); }
    .thumb-overlay { position: absolute; left:0; right:0; bottom:0; padding:10px; background: linear-gradient(180deg, rgba(0,0,0,0) 0%, rgba(0,0,0,0.65) 100%); color: #fff; display:flex; justify-content:space-between; align-items:center; opacity:0; transition: opacity 0.2s ease; }
    .thumb-wrap:hover .thumb-overlay { opacity:1; }
    .overlay-title { font-size:13px; font-weight:600; }
    .overlay-price { font-size:13px; color:#ffd28a; font-weight:700 }
    /* compact grid helpers */
    .gallery-row { display:flex; gap:12px; }
    .gallery-cell { flex:1 1 0; min-width:140px; }
    .gallery-container { position: relative; }
    .gallery-overlay { position:absolute; top:50%; left:0; right:0; transform:translateY(-50%); display:flex; justify-content:space-between; pointer-events:none; }
    .gallery-overlay button { pointer-events:auto; background: rgba(0,0,0,0.5); color:#fff; border: none; padding:8px 10px; border-radius:8px; margin:0 6px; font-weight:700 }
    .gallery-overlay button:hover { background: rgba(0,0,0,0.7); transform: scale(1.03); }
    </style>
""", unsafe_allow_html=True)

# Session state başlatma
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user_data = None
if "token" not in st.session_state:
    st.session_state.token = None
if "leave_data" not in st.session_state:
    st.session_state.leave_data = None
if "page" not in st.session_state:
    st.session_state.page = "menu"
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "gallery_state" not in st.session_state:
    # gallery_state: {"images": [...], "page": 0, "page_size": 4, "preview": None}
    st.session_state.gallery_state = None

# Quick test helper: if URL has ?test=1, prefill demo login and a test chat message
try:
    params = st.query_params
    if params.get("test") == "1":
        if not st.session_state.get("authenticated"):
            # create demo user and auto-login
            demo_email = "test@yatas.com"
            st.session_state.user_data = {
                "id": "test_user",
                "email": demo_email,
                "name": "Test Kullanıcı",
                "department": "",
                "position": "Uzman",
                "personnel_number": "00001234"
            }
            st.session_state.authenticated = True
            st.session_state.token = "demo_token"
            st.session_state.page = "assistant"
            # prefill leave data (demo)
            st.session_state.leave_data = {
                "success": True,
                "total_leave_days": 20,
                "used_leave_days": 7,
                "remaining_leave_days": 13,
                "pending_leave_requests": 2
            }
            # simulate user saying they're in IT
            st.session_state.chat_history = []
            st.session_state.chat_history.append({"role": "user", "content": "ben it ekibindeyim"})
            # Apply the same auto-assign logic so organization view updates
            st.session_state.user_data['department'] = 'IT'
            st.session_state.chat_history.append({"role": "assistant", "content": "✅ Departmanınız 'IT' olarak ayarlandı. Organizasyon sayfasında yeriniz vurgulanacaktır."})
except Exception:
    pass

def verify_sso_credentials(email: str, password: str) -> dict:
    """SSO doğrulama - şifre kontrolü ile."""
    import hashlib
    
    # Demo kullanıcı veritabanı (gerçek ortamda LDAP/AD veya veritabanından gelir)
    # Şifreler SHA256 hash olarak saklanır
    DEMO_USERS = {
        "efirat@yatas.com": {
            "password_hash": hashlib.sha256("302619Ge!!".encode()).hexdigest(),
            "name": "Emrah Fırat",
            "department": "IT",
            "position": "Yazılım Uzmanı",
            "pernr": "00012345"
        },
        "demo@yatas.com": {
            "password_hash": hashlib.sha256("demo123".encode()).hexdigest(),
            "name": "Demo Kullanıcı",
            "department": "IT",
            "position": "Test Uzmanı",
            "pernr": "00099999"
        },
        "admin@yatas.com": {
            "password_hash": hashlib.sha256("admin2025".encode()).hexdigest(),
            "name": "Admin Kullanıcı",
            "department": "Bilgi Teknolojileri",
            "position": "Sistem Yöneticisi",
            "pernr": "00000001"
        }
    }
    
    try:
        email_lower = email.lower()
        
        # 1) Demo kullanıcı listesinde kontrol et
        if email_lower in DEMO_USERS:
            user_data = DEMO_USERS[email_lower]
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            
            if password_hash == user_data["password_hash"]:
                return {
                    "success": True,
                    "token": f"token_{uuid.uuid4().hex[:16]}",
                    "user": {
                        "id": email.split("@")[0],
                        "email": email,
                        "name": user_data["name"],
                        "department": user_data["department"],
                        "position": user_data["position"],
                        "pernr": user_data.get("pernr")
                    },
                    "message": "Giriş başarılı"
                }
            else:
                return {"success": False, "message": "Şifre hatalı"}
        
        # 2) Gerçek SSO endpoint varsa dene (opsiyonel)
        if SSO_CONFIG.get("sso_url") and "https://" in SSO_CONFIG["sso_url"]:
            try:
                payload = {
                    "username": email,
                    "password": password,
                    "client_id": SSO_CONFIG.get("client_id"),
                    "client_secret": SSO_CONFIG.get("client_secret"),
                }
                resp = requests.post(f"{SSO_CONFIG['sso_url']}/login", json=payload, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    return {"success": True, "token": data.get("access_token"), "user": data.get("user"), "message": "SSO başarılı"}
            except Exception:
                pass
        
        # 3) Hiçbiri uymadıysa hata döndür
        return {"success": False, "message": "Kullanıcı bulunamadı veya şifre hatalı"}
        
    except Exception as e:
        return {"success": False, "message": f"Hata: {str(e)}"}


def get_pernr_from_email(email: str) -> dict:
    """Demo: email adresinden PERNR oluşturur veya gerçek API çağrısını dener."""
    try:
        # If demo mode is enabled, return a generated demo PERNR immediately
        if DEMO_MODE:
            domain = email.split("@")[0]
            pernr = f"DEMO{len(domain):04d}"
            return {"success": True, "pernr": pernr, "email": email, "message": "Demo PERNR oluşturuldu (demo mode)"}
        # İlk olarak REST API'ye istek deneyelim (gateway varsa)
        response = requests.post(f"{SAP_API_CONFIG['base_url']}/pernr-from-email", json={"email": email}, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                return {"success": True, "pernr": data.get("pernr"), "email": email}
    except Exception:
        # ignore, demo moduna düşecek
        pass

    # Demo PERNR üret
    domain = email.split("@")[0]
    pernr = f"0000{len(domain):04d}"
    return {"success": True, "pernr": pernr, "email": email, "message": "Demo PERNR oluşturuldu"}

def get_leave_balance_from_sap(personnel_number: str) -> dict:
    """SAP'den RFC çağrısı ile izin bilgisini al - REST API üzerinden"""
    # If demo mode is enabled, return deterministic demo data
    if DEMO_MODE:
        return {
            "success": True,
            "total_leave_days": 20,
            "used_leave_days": 7,
            "remaining_leave_days": 13,
            "pending_leave_requests": 2,
            "year": datetime.now().year,
            "rfc_function": "PT_GET_LEAVE_BALANCE",
            "personnel_id": personnel_number,
            "message": "Demo verisi (demo mode)"
        }

    try:
        # REST API'ye istek gönder
        response = requests.post(
            f"{SAP_API_CONFIG['base_url']}/leave-balance",
            json={
                "pernr": personnel_number,
                "year": datetime.now().year
            },
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                return {
                    "success": True,
                    "total_leave_days": data.get('total_leave_days', 20),
                    "used_leave_days": data.get('used_leave_days', 0),
                    "remaining_leave_days": data.get('remaining_leave_days', 20),
                    "pending_leave_requests": data.get('pending_leave_requests', 0),
                    "year": datetime.now().year,
                    "rfc_function": "PT_GET_LEAVE_BALANCE",
                    "personnel_id": personnel_number,
                    "message": "✅ SAP REST API başarılı",
                    "raw_result": data.get('raw_result', {})
                }
            else:
                return {
                    "success": False,
                    "message": data.get("message", "Veri çekilemedi"),
                    "rfc_function": "PT_GET_LEAVE_BALANCE"
                }
        else:
            return {
                "success": False,
                "message": f"API Hatası: {response.status_code}",
                "rfc_function": "PT_GET_LEAVE_BALANCE"
            }

    except Exception as e:
        # Demo verisi döndür (fallback)
        return {
            "success": True,
            "total_leave_days": 20,
            "used_leave_days": 7,
            "remaining_leave_days": 13,
            "pending_leave_requests": 2,
            "year": datetime.now().year,
            "rfc_function": "PT_GET_LEAVE_BALANCE",
            "personnel_id": personnel_number,
            "message": "Demo verisi (fallback)"
        }

def get_ai_response(user_message: str, leave_data: dict) -> str:
    """AI Asistan cevabı"""
    msg = user_message.lower()
    
    if any(word in msg for word in ["organizasyon", "departman", "bölüm", "organization", "department"]):
        return f"""🏢 **Organizasyon Bilgileriniz:**
🏭 Şirket: Yataş
🏢 Departman: İnsan Kaynakları
👔 Pozisyon: İK Uzmanı
📍 Lokasyon: İstanbul - Merkez Ofis"""
    elif any(word in msg for word in ["izin", "kalan", "leave", "remaining"]):
        return f"""🎯 **İzin Bilgileriniz:**
📅 Toplam: {leave_data['total_leave_days']} gün
✅ Kullanılan: {leave_data['used_leave_days']} gün
⏳ Kalan: {leave_data['remaining_leave_days']} gün
⏱️ Beklemede: {leave_data['pending_leave_requests']} istek"""
    elif any(word in msg for word in ["kullanılan", "used"]):
        return f"📊 {leave_data['used_leave_days']} gün izin kullanmışsınız."
    elif any(word in msg for word in ["kaldı", "kalan", "kaç"]):
        return f"🎯 {leave_data['remaining_leave_days']} gün izin kalmıştır."
    elif any(word in msg for word in ["bekle", "pending", "onay"]):
        return f"⏱️ {leave_data['pending_leave_requests']} istek onay beklemektedir."
    elif any(word in msg for word in ["merhaba", "hello", "selam"]):
        return f"👋 Merhaba! Ben İK Asistanıyım. İzin bilgileriniz, organizasyonunuz veya diğer sorularınız hakkında yardımcı olabilirim."
    else:
        return f"✨ Toplam: {leave_data['total_leave_days']} gün | Kalan: {leave_data['remaining_leave_days']} gün"


def search_products(query: str, max_results: int = 6) -> list:
    """Basit web kazıyıcı: Yataş site aramasından ürün görseli URL'leri döndürür.
    Eğer siteye erişilemezse boş liste döner. Regex ile img URL'leri yakalanır.
    """
    # If demo mode, return a small static set of placeholder images (no external scraping)
    if DEMO_MODE:
        placeholders = [
            f"https://via.placeholder.com/640x400.png?text=Yatas+Demo+{i+1}" for i in range(min(6, max_results))
        ]
        return placeholders

    # Prefer the more robust parser that returns objects with image, price and code
    return search_products_detailed(query, max_results=max_results)


def _parse_price_text(text: str) -> float:
    """Try to extract a numeric price from a string like '1.234,56 TL' or '1,234.56' or '1234.56'"""
    import re
    if not text:
        return 0.0
    # Normalize common number formats
    t = text.strip()
    # remove currency symbols and non-digit/., characters
    t = re.sub(r'[^0-9,\.]', '', t)
    if not t:
        return 0.0
    # If both comma and dot present, decide based on last separator
    if ',' in t and '.' in t:
        if t.rfind(',') > t.rfind('.'):
            # comma is decimal sep, remove dots
            t = t.replace('.', '').replace(',', '.')
        else:
            # dot is decimal sep, remove commas
            t = t.replace(',', '')
    else:
        # Only commas -> treat comma as decimal separator if there are 1 or 2 decimals
        if t.count(',') == 1 and len(t.split(',')[-1]) in (1,2):
            t = t.replace(',', '.')
        else:
            # remove thousand separators (dots)
            t = t.replace(',', '').replace('.', '')
    try:
        return float(t)
    except Exception:
        try:
            return float(t)
        except Exception:
            return 0.0


def search_products_detailed(query: str, max_results: int = 8) -> list:
    """Use BeautifulSoup to parse Yataş (or similar) product listing pages and extract a list of
    dict items: {"image": url, "price": float, "code": str, "title": str}
    This function tries a couple of common listing URLs and falls back to simple image heuristics.
    """
    try:
        from bs4 import BeautifulSoup
    except Exception:
        return []

    headers = {"User-Agent": "Mozilla/5.0"}
    candidates = [
        f"https://www.yatas.com.tr/ara?q={query}",
        f"https://www.yatas.com.tr/arama?q={query}",
        f"https://www.yatas.com.tr/sr?q={query}",
        f"https://www.yatas.com.tr/katalog?q={query}"
    ]

    results = []
    import re

    for url in candidates:
        try:
            r = requests.get(url, timeout=8, headers=headers)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "lxml")

            # Try common product card selectors
            product_selectors = [
                "div.product-item", "div.product-card", "li.product", "div.product-list-item",
                "article.product", "div.urun-item", "div.p-item"
            ]

            cards = []
            for sel in product_selectors:
                found = soup.select(sel)
                if found:
                    cards = found
                    break

            # If no structured cards found, try to infer from link blocks with images
            if not cards:
                anchors = soup.find_all('a', href=True)
                for a in anchors:
                    img = a.find('img')
                    if img and img.get('src'):
                        cards.append(a)

            for c in cards:
                if len(results) >= max_results:
                    break
                # image
                img_tag = None
                if hasattr(c, 'select_one'):
                    img_tag = c.select_one('img')
                else:
                    img_tag = c.find('img')
                img_url = None
                if img_tag:
                    img_url = img_tag.get('data-src') or img_tag.get('src') or img_tag.get('data-original')
                # title
                title = None
                if hasattr(c, 'select_one') and c.select_one('.product-title'):
                    title = c.select_one('.product-title').get_text(strip=True)
                elif hasattr(c, 'find'):
                    h = c.find(['h2','h3','h4'])
                    if h:
                        title = h.get_text(strip=True)
                # price
                price = 0.0
                # Look for price text within card
                price_candidates = []
                if hasattr(c, 'select'):
                    for sel in ['.price', '.product-price', '.fiyat', '.urun-price', '.price-amount']:
                        node = c.select_one(sel)
                        if node:
                            price_candidates.append(node.get_text(strip=True))
                if not price_candidates:
                    # fallback: any element with TL or ₺ nearby
                    text = c.get_text(separator=' ', strip=True)
                    m = re.search(r'([0-9\.,\s]+)\s*(TL|₺)', text, re.IGNORECASE)
                    if m:
                        price_candidates.append(m.group(0))

                for pc in price_candidates:
                    p = _parse_price_text(pc)
                    if p > 0:
                        price = p
                        break

                # product code: try data attributes, or link href containing sku
                code = ""
                if hasattr(c, 'get'):
                    code = c.get('data-sku') or c.get('data-product-code') or c.get('data-id', '')
                if not code:
                    a = c.find('a', href=True) if hasattr(c, 'find') else None
                    if a:
                        href = a.get('href', '')
                        m = re.search(r'(?:sku=|/p/|/urun/|/product/)([A-Za-z0-9\-_%]+)', href)
                        if m:
                            code = m.group(1)

                # sanitize image url: ensure absolute
                if img_url and img_url.startswith('//'):
                    img_url = 'https:' + img_url

                if img_url and (img_url.startswith('http') or img_url.startswith('https')):
                    results.append({"image": img_url, "price": price, "code": code or "", "title": title or ""})

            if results:
                break

        except Exception:
            continue

    # If still empty, fallback to previous simple regex-based image harvest from known CDN
    if not results:
        try:
            r = requests.get(f"https://www.yatas.com.tr/ara?q={query}", timeout=6, headers=headers)
            if r.status_code == 200:
                import re
                found = re.findall(r'https://[^\'\"\s>]+(?:p\d+-img-yatas|p1-img-yatas|banners)[^\'\"\s>]+\.(?:jpg|jpeg|png)', r.text)
                for f in list(dict.fromkeys(found))[:max_results]:
                    results.append({"image": f, "price": 0.0, "code": "", "title": ""})
        except Exception:
            pass

    return results[:max_results]

def logout():
    """Çıkış işlemi"""
    st.session_state.authenticated = False
    st.session_state.user_data = None
    st.session_state.token = None
    st.session_state.leave_data = None
    st.session_state.page = "menu"
    st.session_state.chat_history = []

# GİRİŞ EKRANI
if not st.session_state.authenticated:
    st.markdown('<div class="login-wrapper">', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([0.5, 2, 0.5])
    with col2:
        st.markdown('<div class="login-container">', unsafe_allow_html=True)
        
        # E-posta alanı (kendi label'ımızı kaldırıp Streamlit label'ını kullanıyoruz)
        email = st.text_input(
            "E-POSTA",
            placeholder="user@yatas.com",
            label_visibility="visible",
            key="login_email"
        )
        
        # Şifre alanı (kendi label'ımızı kaldırıp Streamlit label'ını kullanıyoruz)
        password = st.text_input(
            "ŞİFRE",
            type="password",
            placeholder="Şifrenizi girin",
            label_visibility="visible",
            key="login_password"
        )
        
        # Giriş butonu
        if st.button("🚀 Giriş Yap", use_container_width=True, key="login_btn"):
            if email and password:
                with st.spinner("Doğrulanıyor..."):
                    result = verify_sso_credentials(email, password)
                    if result["success"]:
                        # Email'den PERNR bul
                        pernr_result = get_pernr_from_email(email)
                        
                        if pernr_result["success"]:
                            personnel_number = pernr_result["pernr"]
                            st.session_state.user_data = result["user"]
                            st.session_state.user_data["personnel_number"] = personnel_number
                        else:
                            # Demo modda personel numarasını user_data'da kullan
                            personnel_number = result["user"].get("personnel_number", "00001234")
                        
                        st.session_state.authenticated = True
                        st.session_state.token = result["token"]
                        st.session_state.page = "menu"
                        st.success(f"✅ Giriş başarılı! PERNR: {personnel_number}")
                        st.rerun()
                    else:
                        st.error(f"❌ {result['message']}")
            else:
                st.error("❌ Lütfen tüm alanları doldurunuz!")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

# ANA SAYFA
else:
    st.sidebar.title("👤 Kullanıcı Menüsü")
    if st.session_state.user_data:
        st.sidebar.write(f"**{st.session_state.user_data.get('name', 'Kullanıcı')}**")
        st.sidebar.write(f"*{st.session_state.user_data.get('email', '')}*")
        st.sidebar.divider()
    
    if st.sidebar.button("🚪 Çıkış Yap", use_container_width=True):
        logout()
        st.rerun()
    
    # MENU SAYFASI
    if st.session_state.page == "menu":
        # Top title removed; show compact welcome
        st.write(f"Hoş geldiniz, **{st.session_state.user_data.get('name', 'Kullanıcı')}**!")
        st.subheader("Ne yapmak istersiniz?")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button("💼 İK ASİSTANI", use_container_width=True, key="btn_assistant"):
                st.session_state.page = "assistant"
                st.rerun()
        
        with col2:
            if st.button("📊 İZİN BİLGİSİ", use_container_width=True, key="btn_dashboard"):
                st.session_state.page = "dashboard"
                st.rerun()
        
        with col3:
            if st.button("🏢 ORGANİZASYON", use_container_width=True, key="btn_organization"):
                st.session_state.page = "organization"
                st.rerun()

        with col4:
            if st.button("🛒 B2C SİPARİŞ", use_container_width=True, key="btn_b2c"):
                st.session_state.page = "b2c_order"
                # initialize order state
                if "b2c_order_items" not in st.session_state:
                    st.session_state.b2c_order_items = []
                st.rerun()
    
    # İK ASISTAN SAYFASI
    elif st.session_state.page == "assistant":
        if st.session_state.leave_data is None:
            with st.spinner("SAP'den veriler alınıyor..."):
                personnel_number = st.session_state.user_data.get('personnel_number', '00001234')
                st.session_state.leave_data = get_leave_balance_from_sap(personnel_number)
                
                if not st.session_state.leave_data["success"]:
                    st.error(f"⚠️ {st.session_state.leave_data.get('message', 'Veri çekilemedi')}")
        
        leave_data = st.session_state.leave_data
        
        col1, col2 = st.columns([1, 10])
        with col1:
            if st.button("⬅️", key="back_btn"):
                st.session_state.page = "menu"
                st.session_state.chat_history = []
                st.rerun()
        
        with col2:
            st.title("🤖 İK ASİSTANI")
        
        st.write("---")
        
        # Chat container
        chat_container = st.container()
        with chat_container:
            if st.session_state.chat_history:
                for message in st.session_state.chat_history:
                    if message["role"] == "user":
                        st.markdown(f'<div class="chat-message chat-user">{message["content"]}</div>', unsafe_allow_html=True)
                    elif message["role"] == "assistant":
                        response = message["content"]
                        st.markdown(f'<div class="chat-message chat-ai">{response}</div>', unsafe_allow_html=True)
                    elif message["role"] == "image":
                        # render image(s) as a selectable gallery (each image has a 'Sepete Ekle' button)
                        try:
                            img_content = message.get("content")
                            if isinstance(img_content, list) and img_content:
                                # limit columns to max 4 for layout
                                display_list = img_content[:6]
                                cols_per_row = min(4, len(display_list))
                                cols = st.columns(cols_per_row)
                                for i, u in enumerate(display_list):
                                    col = cols[i % cols_per_row]
                                    with col:
                                        try:
                                            st.image(u, use_column_width=True)
                                        except Exception:
                                            st.write("(Görsel yüklenemedi)")
                                        # unique key per image
                                        key = f"add_img_{abs(hash(u))}"
                                        if st.button("➕ Sepete Ekle", key=key):
                                            if "b2c_order_items" not in st.session_state:
                                                st.session_state.b2c_order_items = []
                                            item = {
                                                "id": str(uuid.uuid4())[:8],
                                                "code": "IMG",
                                                "desc": "Seçilen Ürün (galeri)",
                                                "qty": 1.0,
                                                "unit_price": 0.0,
                                                "total": 0.0,
                                                "image_url": u
                                            }
                                            st.session_state.b2c_order_items.append(item)
                                            st.success("Kalem sepete eklendi")
                                            st.rerun()
                            else:
                                # single image
                                try:
                                    st.image(img_content, use_column_width=True)
                                except Exception:
                                    pass
                        except Exception:
                            pass
        
                st.write("---")

                # --- Gallery rendering (pagination + modal/preview) ---
                gs = st.session_state.get("gallery_state")
                if gs and gs.get("images"):
                    images = gs.get("images", [])
                    page = gs.get("page", 0)
                    page_size = gs.get("page_size", 4)
                    total_pages = max(1, (len(images) + page_size - 1) // page_size)
                    page = max(0, min(page, total_pages - 1))
                    start = page * page_size
                    end = start + page_size
                    page_imgs = images[start:end]

                    st.subheader("🔎 Ürün Galerisi")
                    # selection controls (move selected index)
                    sc1, sc2, sc3 = st.columns([1,3,1])
                    with sc1:
                        if st.button("◀ Seç", key="gal_sel_prev"):
                            gs['selected'] = max(0, gs.get('selected', 0) - 1)
                            st.session_state.gallery_state = gs
                            st.rerun()
                    with sc3:
                        if st.button("Seç ▶", key="gal_sel_next"):
                            gs['selected'] = min(len(images) - 1, gs.get('selected', 0) + 1)
                            st.session_state.gallery_state = gs
                            st.rerun()
                    with sc2:
                        st.markdown("<div class='small-muted' style='text-align:center'>Klavye ile gezin: ← ve → tuşları</div>", unsafe_allow_html=True)
                    # page controls
                    ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([1,2,1])
                    with ctrl_col1:
                        if st.button("◀️ Önceki", key=f"gal_prev_{page}"):
                            st.session_state.gallery_state['page'] = max(0, page-1)
                            st.rerun()
                    with ctrl_col2:
                        st.markdown(f"**Sayfa {page+1}/{total_pages} — {len(images)} sonuç**")
                    with ctrl_col3:
                        if st.button("Sonraki ▶️", key=f"gal_next_{page}"):
                            st.session_state.gallery_state['page'] = min(total_pages-1, page+1)
                            st.rerun()

                        # gallery container so overlay buttons can be positioned absolutely
                        st.markdown("<div class='gallery-container'>", unsafe_allow_html=True)
                        # overlay control buttons (visual) - will be wired to the Streamlit selection buttons via JS
                        overlay_html = """
                        <div class='gallery-overlay'>
                            <button id='gal_overlay_prev' aria-label='previous'>&larr;</button>
                            <button id='gal_overlay_next' aria-label='next'>&rarr;</button>
                        </div>
                        """
                        st.markdown(overlay_html, unsafe_allow_html=True)

                        cols = st.columns(len(page_imgs))
                for i, u in enumerate(page_imgs):
                    col = cols[i]
                    with col:
                        # u may be a dict with keys image, price, code, title or a plain url
                        if isinstance(u, dict):
                            img_url = u.get('image')
                            price = u.get('price', 0.0) or 0.0
                            code = u.get('code', '') or ''
                            title = u.get('title', '') or ''
                        else:
                            img_url = u
                            price = 0.0
                            code = ''
                            title = ''
                        try:
                            # determine global index
                            global_index = start + i
                            sel = gs.get('selected', 0)
                            # add selected highlight class if selected
                            highlight_style = "border:2px solid #ffd28a; box-shadow:0 4px 18px rgba(0,0,0,0.6);" if global_index == sel else ""
                            title_html = (f"<div class='overlay-title'>{title}</div>") if title else ""
                            price_html = (f"<div class='overlay-price'>{price:.2f} TL</div>") if price and price > 0 else ""
                            img_html = (
                                f"<div class='thumb-wrap' style='{highlight_style}'>"
                                f"<img class='thumb-img' src='{img_url}'/>"
                                f"<div class='thumb-overlay'>{title_html}<div style='flex:1'></div>{price_html}</div>"
                                f"</div>"
                            )
                            st.markdown(img_html, unsafe_allow_html=True)
                        except Exception:
                            st.write("(Görsel yüklenemedi)")
                        # preview and add buttons
                        key_preview = f"gal_preview_{start+i}_{abs(hash(str(img_url)))}"
                        key_add = f"gal_add_{start+i}_{abs(hash(str(img_url)))}"
                        if st.button("🔍 Önizle", key=key_preview):
                            st.session_state.gallery_state['preview'] = u
                            st.rerun()
                        if st.button("➕ Sepete Ekle", key=key_add):
                            if "b2c_order_items" not in st.session_state:
                                st.session_state.b2c_order_items = []
                            item = {
                                "id": str(uuid.uuid4())[:8],
                                "code": code or "IMG",
                                "desc": title or "Seçilen Ürün (galeri)",
                                "qty": 1.0,
                                "unit_price": float(price) if price else 0.0,
                                "total": round((float(price) if price else 0.0) * 1.0, 2),
                                "image_url": img_url
                            }
                            st.session_state.b2c_order_items.append(item)
                            st.success("Kalem sepete eklendi")
                            st.rerun()

                    # preview modal / large preview
                    preview = st.session_state.gallery_state.get('preview')
                    if preview:
                        st.write("---")
                        st.subheader("📷 Büyük Önizleme")
                        # preview may be dict or url
                        if isinstance(preview, dict):
                            p_img = preview.get('image')
                            p_price = preview.get('price', 0.0) or 0.0
                            p_code = preview.get('code', '') or ''
                            p_title = preview.get('title', '') or ''
                        else:
                            p_img = preview
                            p_price = 0.0
                            p_code = ''
                            p_title = ''
                        try:
                            st.markdown(f"<img class='preview-img' src='{p_img}'/>", unsafe_allow_html=True)
                        except Exception:
                            st.write("(Önizleme yüklenemedi)")
                        if p_title:
                            st.write(f"**{p_title}**")
                        if p_price and p_price > 0:
                            st.write(f"Fiyat: {p_price:.2f} TL")
                        pc1, pc2, pc3 = st.columns([1,1,1])
                        with pc1:
                            if st.button("✖ Kapat", key=f"gal_close_{abs(hash(str(p_img)))}"):
                                st.session_state.gallery_state['preview'] = None
                                st.rerun()
                        with pc2:
                            if st.button("➕ Sepete Ekle (Büyük)", key=f"gal_add_preview_{abs(hash(str(p_img)))}"):
                                if "b2c_order_items" not in st.session_state:
                                    st.session_state.b2c_order_items = []
                                item = {
                                    "id": str(uuid.uuid4())[:8],
                                    "code": p_code or "IMG",
                                    "desc": p_title or "Seçilen Ürün (önizleme)",
                                    "qty": 1.0,
                                    "unit_price": float(p_price) if p_price else 0.0,
                                    "total": round((float(p_price) if p_price else 0.0) * 1.0, 2),
                                    "image_url": p_img
                                }
                                st.session_state.b2c_order_items.append(item)
                                st.success("Kalem sepete eklendi")
                                st.session_state.gallery_state['preview'] = None
                                st.rerun()
                        with pc3:
                            st.write("")

                        # Inject JS to capture left/right arrow keys, hide the separate control buttons, and wire overlay clicks
                        js = """
                        <script>
                        (function(){
                            function findControlButtons(){
                                const buttons = Array.from(document.querySelectorAll('button'));
                                const prevBtn = buttons.find(b => b.innerText && b.innerText.trim().startsWith('◀ Seç'));
                                const nextBtn = buttons.find(b => b.innerText && b.innerText.trim().endsWith('Seç ▶'));
                                return {prevBtn, nextBtn};
                            }

                            // hide the separate Streamlit control buttons visually (if found)
                            setTimeout(function(){
                                const b = findControlButtons();
                                if (b.prevBtn) { b.prevBtn.style.display = 'none'; }
                                if (b.nextBtn) { b.nextBtn.style.display = 'none'; }
                            }, 500);

                            document.addEventListener('keydown', function(e) {
                                try {
                                    const key = e.key;
                                    if (key === 'ArrowLeft' || key === 'ArrowRight') {
                                        const b = findControlButtons();
                                        if (key === 'ArrowLeft' && b.prevBtn) { b.prevBtn.click(); }
                                        if (key === 'ArrowRight' && b.nextBtn) { b.nextBtn.click(); }
                                    }
                                } catch(err){console.log(err)}
                            });

                            // wire overlay buttons to click the hidden Streamlit buttons
                            function wireOverlay(){
                                const overlayPrev = document.getElementById('gal_overlay_prev');
                                const overlayNext = document.getElementById('gal_overlay_next');
                                const b = findControlButtons();
                                if (overlayPrev){ overlayPrev.addEventListener('click', function(){ if (b.prevBtn) b.prevBtn.click(); }); }
                                if (overlayNext){ overlayNext.addEventListener('click', function(){ if (b.nextBtn) b.nextBtn.click(); }); }
                            }

                            // try wiring repeatedly until Streamlit buttons exist
                            let tries = 0;
                            const t = setInterval(function(){
                                try { wireOverlay(); tries++; if (tries>20) clearInterval(t); } catch(e){}
                            }, 300);
                        })();
                        </script>
                        """
                        st.markdown(js, unsafe_allow_html=True)

                        # close gallery container
                        st.markdown("</div>", unsafe_allow_html=True)

        
        # Input form
        with st.form(key="chat_form", clear_on_submit=True):
            col1, col2 = st.columns([9, 1])
            with col1:
                user_input = st.text_input("💬 Sorunuzu yazın...", placeholder="Örn: Kaç günüm kaldı?")
            with col2:
                send_btn = st.form_submit_button("📤")
            
            if send_btn and user_input:
                text = user_input.strip().lower()
                # Basit eşleme: kullanıcı "IT" ekibinde olduğunu belirtirse department güncellensin
                it_phrases = [
                    "ben it ekibindenim",
                    "ben it ekibindeyim",
                    "ben it'teyim",
                    "ben itte çalışıyorum",
                    "ben itteyim",
                    "it ekibindeyim",
                ]

                # Product gallery trigger (ör: "yatak")
                product_keywords = ["yatak", "yataklar", "yorgan", "yastık", "yastik"]
                if any(k in text for k in product_keywords):
                    st.session_state.chat_history.append({"role": "user", "content": user_input})
                    imgs = search_products("yatak", max_results=12)
                    if imgs:
                        # set gallery state for pagination + preview and selected index
                        st.session_state.gallery_state = {"images": imgs, "page": 0, "page_size": 4, "preview": None, "selected": 0}
                        st.session_state.chat_history.append({"role": "assistant", "content": "Aşağıdaki ürünlere göz atın — görsele tıklayın veya 'Önizle' ile büyütün. Sepete eklemek için 'Sepete Ekle' kullanın."})
                    else:
                        st.session_state.chat_history.append({"role": "assistant", "content": "Üzgünüm, ürün görselleri bulunamadı."})
                    st.rerun()

                if any(p in text for p in it_phrases) or ("it" in text and "ekip" in text):
                    st.session_state.user_data = st.session_state.user_data or {}
                    st.session_state.user_data['department'] = 'IT'
                    st.session_state.chat_history.append({"role": "user", "content": user_input})
                    st.session_state.chat_history.append({"role": "assistant", "content": "✅ Departmanınız 'IT' olarak ayarlandı. Organizasyon sayfasında yeriniz vurgulanacaktır."})
                    st.rerun()
                else:
                    st.session_state.chat_history.append({"role": "user", "content": user_input})
                    ai_response = get_ai_response(user_input, leave_data)
                    st.session_state.chat_history.append({"role": "assistant", "content": ai_response})
                    st.rerun()
    
    # DASHBOARD SAYFASI
    elif st.session_state.page == "dashboard":
        if st.session_state.leave_data is None:
            with st.spinner("SAP'den veriler alınıyor..."):
                personnel_number = st.session_state.user_data.get('personnel_number', '00001234')
                st.session_state.leave_data = get_leave_balance_from_sap(personnel_number)
        
        leave_data = st.session_state.leave_data
        
        col1, col2 = st.columns([1, 10])
        with col1:
            if st.button("⬅️", key="back_dash"):
                st.session_state.page = "menu"
                st.rerun()
        
        with col2:
            st.title("📊 İZİN BİLGİSİ")
        
        st.write("---")
        
        if leave_data["success"]:
            st.success("✅ Veriler başarıyla alındı")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("📅 Toplam İzin", f"{leave_data['total_leave_days']} gün")
            with col2:
                st.metric("✅ Kullanılan", f"{leave_data['used_leave_days']} gün")
            with col3:
                st.metric("⏳ Kalan", f"{leave_data['remaining_leave_days']} gün")
            with col4:
                st.metric("⏱️ Beklemede", f"{leave_data['pending_leave_requests']}")
            
            st.write("---")
            st.subheader("📊 Detaylı Görünüm")
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown('<div class="leave-card"><div class="leave-label">🎯 Kalan İzin Günü</div><div class="leave-number">' + str(leave_data["remaining_leave_days"]) + '</div></div>', unsafe_allow_html=True)
            
            with col2:
                st.markdown('<div class="leave-card"><div class="leave-label">📋 Beklemede olan İstek</div><div class="leave-number">' + str(leave_data["pending_leave_requests"]) + '</div></div>', unsafe_allow_html=True)
            
            st.write("---")
            st.subheader("🔧 RFC Çağrısı Sonuçları")
            st.json(leave_data)
        else:
            st.error(f"❌ Hata: {leave_data.get('message', 'Bilinmeyen hata')}")
            st.write("---")
            st.subheader("🔧 RFC Hata Detayları")
            st.json(leave_data)

    # ORGANİZASYON SAYFASI
    elif st.session_state.page == "organization":
        col1, col2 = st.columns([1, 10])
        with col1:
            if st.button("⬅️", key="back_org"):
                st.session_state.page = "menu"
                st.rerun()
        
        with col2:
            st.title("🏢 ORGANİZASYON BİLGİSİ")
        
        st.write("---")
        
        # Organizasyon verileri
        org_data = {
            "Şirket": "Yataş",
            "Departman": "İnsan Kaynakları",
            "Pozisyon": "İK Uzmanı",
            "Lokasyon": "İstanbul - Merkez Ofis",
            "Başkan": "Cengiz Ateş",
            "Müdür": "Ahmet Yılmaz",
            "Çalışan Sayısı": 250,
            "Kuruluş Yılı": 1985
        }
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📋 Genel Bilgiler")
            for key, value in list(org_data.items())[:4]:
                st.write(f"**{key}:** {value}")
        
        with col2:
            st.subheader("👥 Yönetim")
            for key, value in list(org_data.items())[4:6]:
                st.write(f"**{key}:** {value}")
        
        st.write("---")
        st.subheader("📊 Kuruluş Hiyerarşisi")
        
        # Simple chart for organization structure
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        from matplotlib.patches import FancyBboxPatch
        import numpy as np
        
        fig, ax = plt.subplots(figsize=(12, 8))
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 10)
        ax.axis('off')
        
        # CEO
        ceo_box = FancyBboxPatch((3.5, 8.5), 3, 0.8, boxstyle="round,pad=0.1", 
                                  edgecolor='#667eea', facecolor='#667eea', linewidth=2)
        ax.add_patch(ceo_box)
        ax.text(5, 8.9, 'CEO\nYönetim Kurulu', ha='center', va='center', fontsize=10, 
               fontweight='bold', color='white')
        
        # Departments
        departments = [
            ('İK\nDepartmanı', 1, 6.5, '#764ba2'),
            ('Satış\nDepartmanı', 3.5, 6.5, '#764ba2'),
            ('Üretim\nDepartmanı', 6, 6.5, '#764ba2'),
            ('Muhasebe\nDepartmanı', 8.5, 6.5, '#764ba2')
        ]
        
        for dept, x, y, color in departments:
            dept_box = FancyBboxPatch((x-0.6, y-0.4), 1.2, 0.8, boxstyle="round,pad=0.05",
                                      edgecolor=color, facecolor=color, linewidth=2)
            ax.add_patch(dept_box)
            ax.text(x, y, dept, ha='center', va='center', fontsize=9, 
                   fontweight='bold', color='white')
            # Line from CEO to department
            ax.plot([5, x], [8.5, y+0.4], 'k-', linewidth=1)
        
        # Current position
        current_box = FancyBboxPatch((3.5-0.6, 4.5-0.4), 1.2, 0.8, boxstyle="round,pad=0.05",
                                     edgecolor='#FFA500', facecolor='#FFA500', linewidth=2.5)
        ax.add_patch(current_box)
        ax.text(3.5, 4.5, '👤 SİZ\n(İK Uzmanı)', ha='center', va='center', fontsize=9,
               fontweight='bold', color='white')
        # Line from İK to current position
        ax.plot([1, 3.5], [6.5, 4.9], 'k-', linewidth=1)
        
        st.pyplot(fig)
        
        st.write("---")
        st.subheader("📈 İstatistikler")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("👥 Toplam Çalışan", 250)
        with col2:
            st.metric("🎂 Kuruluş Yılı", 1985)
        with col3:
            st.metric("🏭 Şube Sayısı", 5)
        with col4:
            st.metric("🌍 Ülke", "Türkiye")

    # B2C SİPARİŞ SAYFASI
    elif st.session_state.page == "b2c_order":
        # initialize items list if not present
        if "b2c_order_items" not in st.session_state:
            st.session_state.b2c_order_items = []

        col1, col2 = st.columns([1, 10])
        with col1:
            if st.button("⬅️", key="back_b2c"):
                st.session_state.page = "menu"
                st.rerun()

        with col2:
            st.title("🛒 B2C Sipariş Oluştur")

        st.write("---")

        # Order header
        with st.form(key="b2c_header_form"):
            shop_col, date_col, pers_col = st.columns([3, 2, 2])
            with shop_col:
                store_code = st.text_input("Mağaza Kodu", value="001")
                customer = st.text_input("Müşteri / Fatura Adres", value="Bireysel Müşteri")
            with date_col:
                doc_date = st.date_input("Belge Tarihi", value=datetime.now())
            with pers_col:
                personnel_no = st.text_input("Personel no.", value=st.session_state.user_data.get('personnel_number', '00001234') if st.session_state.user_data else "00001234")
            st.form_submit_button("Güncelle")

        st.write("---")

        # Line item form
        st.subheader("Kalem Ekle")
        with st.form(key="b2c_line_form", clear_on_submit=True):
            c1, c2, c3, c4 = st.columns([2, 5, 2, 2])
            with c1:
                mat_code = st.text_input("Malzeme Kodu")
            with c2:
                mat_desc = st.text_input("Malzeme Tanımı")
            with c2:
                image_url = st.text_input("Ürün Görseli (opsiyonel)", placeholder="https://...")
            with c3:
                qty = st.number_input("Miktar", min_value=0.0, value=1.0, step=1.0)
            with c4:
                price = st.number_input("Birim Fiyat", min_value=0.0, value=0.0, step=0.01)

            add_line = st.form_submit_button("Kalem Ekle")
            if add_line:
                item = {
                    "id": str(uuid.uuid4())[:8],
                    "code": mat_code,
                    "desc": mat_desc,
                    "qty": float(qty),
                    "unit_price": float(price),
                    "total": round(float(qty) * float(price), 2),
                    "image_url": image_url if image_url else ""
                }
                st.session_state.b2c_order_items.append(item)
                st.success("Kalem eklendi")
                st.rerun()

        # Items table and totals
        st.write("---")
        st.subheader("Sipariş Kalemleri")
        items = st.session_state.get("b2c_order_items", [])
        if items:
            df = pd.DataFrame(items)
            df_display = df[["code", "desc", "qty", "unit_price", "total"]].rename(columns={"code":"Kod","desc":"Açıklama","qty":"Miktar","unit_price":"Birim Fiyat","total":"Tutar"})
            st.dataframe(df_display, use_container_width=True)

            subtotal = df['total'].sum()
            tax = round(subtotal * 0.18, 2)
            grand_total = round(subtotal + tax, 2)

            cola, colb, colc = st.columns([3,2,2])
            with colc:
                st.metric("Ara Toplam", f"{subtotal:.2f} TL")
                st.metric("KDV (18%)", f"{tax:.2f} TL")
                st.metric("Genel Toplam", f"{grand_total:.2f} TL")

            # Show thumbnails for items that have an image_url
            images_to_show = [it for it in items if it.get("image_url")]
            if images_to_show:
                st.write("---")
                st.subheader("Ürün Görselleri")
                # display in rows of up to 4
                per_row = 4
                for i in range(0, len(images_to_show), per_row):
                    row = images_to_show[i:i+per_row]
                    cols = st.columns(len(row))
                    for j, it in enumerate(row):
                        with cols[j]:
                            try:
                                img_html = f"<div class='thumb-wrap'><img class='thumb-img' src='{it.get('image_url')}'/></div>"
                                st.markdown(img_html, unsafe_allow_html=True)
                            except Exception:
                                st.write("(Görsel yüklenemedi)")
                            st.markdown(f"<div class='small-muted'><b>{it.get('desc','')}</b></div>", unsafe_allow_html=True)
                            if st.button("Sil", key=f"del_item_{it['id']}"):
                                # remove specific item
                                st.session_state.b2c_order_items = [x for x in st.session_state.b2c_order_items if x['id'] != it['id']]
                                st.rerun()

            # allow removing last item
            if st.button("Son Kalemi Kaldır", help="Son eklenen kalemi sil"):
                st.session_state.b2c_order_items.pop()
                st.rerun()

            if st.button("Siparişi Kaydet", key="save_order"):
                order_id = f"B2C-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:6]}"
                st.success(f"Sipariş kaydedildi: {order_id}")
                st.info(f"Toplam: {grand_total:.2f} TL | Kalem adedi: {len(items)}")
                # reset items
                st.session_state.b2c_order_items = []
        else:
            st.info("Henüz sipariş kalemi yok. Üstten kalem ekleyin.")

    # AĞ BAĞLANTISI HATASI
    elif st.session_state.page == "connection_error":
        st.title("❌ Bağlantı Hatası")
        st.write("SAP sistemine bağlanırken bir hata oluştu.")
        st.write("Lütfen ağ bağlantınızı kontrol edin ve tekrar deneyin.")
        
        if st.button("🔄 Yeniden Dene", use_container_width=True):
            st.session_state.page = "menu"
            st.rerun()
    
    # HATA SAYFASI
    elif st.session_state.page == "error":
        st.title("❌ Bir Hata Oluştu")
        st.write("Beklenmeyen bir hata meydana geldi.")
        st.write("Hata detayları:")
        st.json(st.session_state.error_details)
        
        if st.button("🔄 Yeniden Dene", use_container_width=True):
            st.session_state.page = "menu"
            st.rerun()
