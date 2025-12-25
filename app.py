import streamlit as st
import os
import logging
import sys
import traceback
import requests
import json
from datetime import datetime, timedelta
import pandas as pd
import uuid
from azure.data.tables import TableServiceClient
from bs4 import BeautifulSoup


def scrape_with_playwright(sites, timeout=20000):
    """Try to use Playwright to render JS-heavy pages and return collected product dicts.
    Returns None if Playwright is not available or an empty list if nothing collected.
    """
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return None

    collected = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            for site in sites:
                try:
                    page.goto(site["url"], timeout=timeout)
                    page.wait_for_load_state('networkidle', timeout=timeout)
                    html = page.content()
                    soup = BeautifulSoup(html, 'html.parser')

                    # Reuse same heuristics as non-js scraper
                    cards = []
                    for sel in ('.product-card', '.product-item', '.productListContent-item', '.prd', '.p-card'):
                        cards = soup.select(sel)
                        if cards:
                            break
                    if not cards:
                        cards = soup.select('a[href*="/p/"]')[:20]

                    for idx, card in enumerate(cards[:20], start=1):
                        try:
                            title = None
                            for tsel in ('.product-title', '.product-name', 'h3', 'h4', '.prd-name', '.p-card__title'):
                                t = card.select_one(tsel) if hasattr(card, 'select_one') else None
                                if t and t.get_text(strip=True):
                                    title = t.get_text(strip=True)
                                    break
                            if not title:
                                title = card.get_text(strip=True)[:80]

                            price = 0.0
                            for psel in ('.price', '.product-price', '.fiyat', '.p-card__price', '.discountPrice'):
                                p = card.select_one(psel) if hasattr(card, 'select_one') else None
                                if p and p.get_text(strip=True):
                                    price = _parse_price_text(p.get_text(strip=True))
                                    break

                            img = None
                            if hasattr(card, 'select_one'):
                                im = card.select_one('img')
                                if im:
                                    img = im.get('data-src') or im.get('src') or None
                                    if img and img.startswith('//'):
                                        img = 'https:' + img

                            url = ''
                            if hasattr(card, 'get'):
                                a = card if card.name == 'a' else card.select_one('a')
                                if a and a.get('href'):
                                    url = a.get('href')
                                    if url.startswith('/'):
                                        parts = site['url'].split('/')
                                        url = parts[0] + '//' + parts[2] + url

                            collected.append({
                                'product_name': title or 'Ürün',
                                'price': price or 0.0,
                                'image_url': img or '',
                                'source': site['name'],
                                'url': url,
                                'rank': idx
                            })
                        except Exception:
                            continue
                except Exception:
                    continue
            try:
                browser.close()
            except Exception:
                pass
    except Exception:
        return None

    return collected

import hashlib
import secrets
import string
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from urllib.parse import urlencode

# Setup simple file logger for debugging
logger = logging.getLogger("yatas_app_debug")
if not logger.handlers:
    fh = logging.FileHandler("app_debug.log")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(fh)
    logger.setLevel(logging.DEBUG)

# Sayfa yapılandırması
logger.debug("Starting app.py")

# set_page_config must be the first Streamlit command in the script
st.set_page_config(page_title="Yataş Giriş", layout="wide")

# Global exception hook to capture uncaught exceptions in Streamlit worker threads
def _handle_uncaught(exc_type, exc_value, exc_tb):
    try:
        logger.exception("Uncaught exception", exc_info=(exc_type, exc_value, exc_tb))
    except Exception:
        # fallback to printing
        print("Exception in excepthook:")
        traceback.print_exception(exc_type, exc_value, exc_tb)

sys.excepthook = _handle_uncaught

# Log initial session/query state for diagnostics
try:
    logger.debug("Initial session_state keys: %s", list(st.session_state.keys()))
    logger.debug("Initial query_params: %s", dict(st.query_params))
except Exception:
    logger.exception("Failed to log initial session/query params")

# (Header removed) Top banner/logo and big title intentionally omitted from UI per request.

# Load configuration from environment to avoid embedding secrets in code
SSO_CONFIG = {
    "sso_url": os.getenv("SSO_URL", ""),
    "client_id": os.getenv("SSO_CLIENT_ID", ""),
    "client_secret": os.getenv("SSO_CLIENT_SECRET", ""),
    "tenant_id": os.getenv("SSO_TENANT_ID", "a9967bb3-3814-4e7f-bee0-428a98fffca7"),
    "redirect_uri": os.getenv("SSO_REDIRECT_URI", "http://localhost:8501")
}

# Feature flags
ENABLE_PASSWORD_RESET = False
logger.debug("ENABLE_PASSWORD_RESET=%s", ENABLE_PASSWORD_RESET)

# Genel paylaşılacak taban URL (reset linkleri vb. için).
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL") or SSO_CONFIG.get("redirect_uri", "http://localhost:8501")

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

# Azure Table Storage Konfigürasyonu (for project analysis)
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
AZURE_TABLE_NAME = os.getenv("AZURE_TABLE_NAME", "TopProductsDaily")

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

/* Hide Streamlit chrome and decorations */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header { visibility: hidden; }
.stDecoration, .stDeployButton { display: none !important; }

/* Minimal app background and input/button styling to avoid large floating boxes */
.stApp { background: #f5f5f5 !important; }
.stApp .stTextInput input, .stApp input, .stApp textarea, .stApp select {
    background: #fff !important;
    box-shadow: none !important;
    border-radius: 8px !important;
    border: 1px solid rgba(0,0,0,0.06) !important;
}
.stApp .stButton>button { box-shadow: none !important; border-radius: 8px !important; }

/* Keep login area padded and remove custom card shadows */
[data-testid="stAppViewContainer"] { padding: 20px !important; }
.login-wrapper, .card-section, .stTextInput, .stButton { box-shadow: none !important; background: transparent !important; }

/* Chat and gallery helpers (kept minimal) */
.chat-user { background-color: #667eea; color: white; text-align: right; border-radius: 12px; margin-left: 40px; box-shadow: 0 2px 8px rgba(102,126,234,0.3); }
.chat-ai { background-color: #f0f0f0; color: #333; border-left: 4px solid #764ba2; margin-right: 40px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
.card-section { background: #0f1113; border: 1px solid rgba(255,255,255,0.03); padding: 18px; border-radius: 12px; margin-bottom: 18px; }
.thumb-img { width:100%; height:160px; object-fit:cover; border-radius:10px; border:1px solid rgba(255,255,255,0.04); }
.thumb-wrap { padding:6px; background: #0b0c0e; border-radius:10px; position:relative; overflow:hidden; }
.thumb-overlay { position:absolute; left:0; right:0; bottom:0; padding:10px; background: linear-gradient(180deg, rgba(0,0,0,0) 0%, rgba(0,0,0,0.65) 100%); color:#fff; display:flex; justify-content:space-between; align-items:center; opacity:0; transition: opacity 0.2s ease; }
.thumb-wrap:hover .thumb-overlay { opacity:1; }

/* Responsive tweaks */
@media (max-width: 600px) {
  [data-testid="stAppViewContainer"] { padding: 12px !important; }
}
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

def generate_azure_ad_login_url() -> str:
    """Azure AD Authorization Code Flow login URL'sini oluştur."""
    from urllib.parse import urlencode
    
    client_id = SSO_CONFIG.get("client_id")
    redirect_uri = SSO_CONFIG.get("redirect_uri")
    tenant_id = SSO_CONFIG.get("tenant_id", "common")
    
    params = {
        "client_id": client_id,
        "response_type": "code",
        "scope": "https://graph.microsoft.com/User.Read",
        "redirect_uri": redirect_uri,
        "prompt": "select_account"
    }
    
    auth_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize?{urlencode(params)}"
    return auth_url


def _normalize_analysis_items(items):
    """Normalize various scraped/top10 item formats into the schema used by the UI.
    Desired keys: product_name, price (float|None), image_url, url, rank
    """
    out = []
    for idx, it in enumerate(items or []):
        if not isinstance(it, dict):
            continue
        d = dict(it)  # copy
        # map common keys
        if 'product_name' not in d and 'name' in d:
            d['product_name'] = d.get('name')
        if 'product_name' not in d and 'title' in d:
            d['product_name'] = d.get('title')
        if 'image_url' not in d and 'image' in d:
            d['image_url'] = d.get('image')
        if 'image_url' not in d and 'image_url' in d:
            d['image_url'] = d.get('image_url')
        if 'url' not in d and 'link' in d:
            d['url'] = d.get('link')
        # normalize price to float if possible
        p = d.get('price')
        if p is not None and not isinstance(p, (int, float)):
            try:
                s = str(p)
                m = re.search(r"[0-9][0-9.,]{0,}", s)
                if m:
                    d['price'] = float(m.group(0).replace(',',''))
                else:
                    d['price'] = None
            except Exception:
                d['price'] = None
        # ensure rank
        if 'rank' not in d:
            try:
                d['rank'] = int(d.get('rank', idx+1))
            except Exception:
                d['rank'] = idx+1
        # ensure site/source information when available
        if 'site' not in d:
            d['site'] = d.get('source') or d.get('site_name') or d.get('marketplace') or None
        out.append(d)
    return out

def exchange_code_for_token(code: str) -> dict:
    """Authorization code'u token ile değiştir."""
    try:
        token_url = f"https://login.microsoftonline.com/{SSO_CONFIG.get('tenant_id', 'common')}/oauth2/v2.0/token"
        
        payload = {
            "client_id": SSO_CONFIG.get("client_id"),
            "client_secret": SSO_CONFIG.get("client_secret"),
            "code": code,
            "redirect_uri": SSO_CONFIG.get("redirect_uri"),
            "grant_type": "authorization_code",
            "scope": "https://graph.microsoft.com/User.Read"
        }
        
        response = requests.post(token_url, data=payload, timeout=10)
        
        if response.status_code == 200:
            token_data = response.json()
            return {"success": True, "token": token_data.get("access_token")}
        else:
            error = response.json().get("error_description", "Bilinmeyen hata")
            return {"success": False, "message": f"Token hatası: {error}"}
    except Exception as e:
        return {"success": False, "message": f"Token değişim hatası: {str(e)}"}

def get_user_from_graph(access_token: str) -> dict:
    """Graph API'den kullanıcı bilgilerini al."""
    try:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get("https://graph.microsoft.com/v1.0/me", headers=headers, timeout=10)
        
        if response.status_code == 200:
            user = response.json()
            return {
                "success": True,
                "user": {
                    "id": user.get("id", ""),
                    "email": user.get("mail", user.get("userPrincipalName", "")),
                    "name": user.get("displayName", ""),
                    "department": user.get("department", ""),
                    "position": user.get("jobTitle", ""),
                    "pernr": ""
                }
            }
        else:
            return {"success": False, "message": "Kullanıcı bilgileri alınamadı"}
    except Exception as e:
        return {"success": False, "message": f"Graph API hatası: {str(e)}"}

# ============ USER MANAGEMENT FUNCTIONS ============

USERS_FILE = "users.json"

def load_users() -> dict:
    """users.json dosyasından kullanıcıları yükle."""
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        st.error(f"Kullanıcılar yüklenemedi: {str(e)}")
    return {"users": []}

def save_users(data: dict):
    """Kullanıcıları users.json'a kaydet."""
    try:
        logger.debug("Saving users.json with %d users", len(data.get("users", [])))
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.debug("users.json saved")
        return True
    except Exception as e:
        logger.exception("Kullanıcılar kaydedilemedi: %s", str(e))
        st.error(f"Kullanıcılar kaydedilemedi: {str(e)}")
        return False

def find_user_by_email(email: str) -> dict:
    """Email'e göre kullanıcı bul."""
    users_data = load_users()
    for user in users_data.get("users", []):
        if user.get("email", "").lower() == email.lower():
            return user
    return None

def add_user(email: str, name: str, department: str, position: str, role: str = "user", pernr: str = "") -> bool:
    """Yeni kullanıcı ekle."""
    users_data = load_users()
    
    # Kontrolü yap
    if find_user_by_email(email):
        return False  # Kullanıcı zaten var
    
    # Varsayılan şifre: Şifre sıfırlama gerektirecek şekilde boş
    new_user = {
        "id": str(uuid.uuid4()),
        "email": email,
        "name": name,
        "password_hash": "",  # Boş, şifre reset linkini gönder veya geçici şifre üret
        "department": department,
        "position": position,
        "role": role,
        "permissions": ["read", "write"] if role == "user" else ["read", "write", "delete", "admin"],
        "pernr": pernr,
        "is_active": True,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "last_login": None,
        "password_reset_token": secrets.token_urlsafe(32),
        "password_reset_expires": (datetime.utcnow() + timedelta(hours=24)).isoformat() + "Z"
    }
    
    users_data["users"].append(new_user)
    return save_users(users_data)


def _generate_temp_password(length: int = 8) -> str:
    """Harf+rakam karışık geçici şifre üretir."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def request_password_reset(email: str) -> bool:
    """Geçici 8 karakterli şifre üretir, kullanıcıya yazar ve e-postayla gönderir."""
    logger.debug("request_password_reset start for %s", email)
    user = find_user_by_email(email)
    if not user:
        logger.debug("request_password_reset: user not found %s", email)
        return False

    temp_password = _generate_temp_password(8)
    temp_hash = hashlib.sha256(temp_password.encode()).hexdigest()

    users_data = load_users()
    updated = False
    for u in users_data.get("users", []):
        if u.get("email", "").lower() == email.lower():
            u["password_hash"] = temp_hash
            # tokenları temizle
            u["password_reset_token"] = None
            u["password_reset_expires"] = None
            updated = True
            break

    if not updated:
        logger.debug("request_password_reset: no user updated for %s", email)
        return False

    save_ok = save_users(users_data)
    logger.debug("request_password_reset: save_users returned %s", save_ok)

    res = send_password_reset_email(email, temp_password, user.get("name", ""))
    logger.debug("request_password_reset: send_password_reset_email returned %s", res)
    return res

def update_user_active(email: str, is_active: bool) -> bool:
    """Kullanıcı aktiflik durumunu günceller."""
    users_data = load_users()
    updated = False
    for u in users_data.get("users", []):
        if u.get("email", "").lower() == email.lower():
            u["is_active"] = is_active
            updated = True
            break
    if not updated:
        return False
    return save_users(users_data)

def send_password_reset_email(email: str, temp_password: str, user_name: str) -> bool:
    """Şifre sıfırlama e-postası: geçici şifreyi iletir."""
    try:
        # SMTP bilgileri (SendGrid, Gmail vb. kullanabilir)
        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        sender_email = os.getenv("SENDER_EMAIL", "noreply@yatas.com")
        sender_password = os.getenv("SENDER_PASSWORD", "")
        
        if not sender_password:
            st.warning("SMTP servisi yapılandırılmadı. Konsola geçici şifre yazılıyor.")
            logger.info(f"[PASSWORD RESET] Email: {email}, Temporary Password: {temp_password}")
            print(f"[PASSWORD RESET] Email: {email}, Temporary Password: {temp_password}")
            return True

        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = email
        msg['Subject'] = 'Yataş Portal - Geçici Şifre'
        
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <h2>Geçici Şifreniz</h2>
                <p>Merhaba {user_name},</p>
                <p>Hesabınız için yeni geçici şifreniz aşağıdadır. Giriş yaptıktan sonra profilinizden değiştirmenizi öneririz.</p>
                <p style="font-size:18px; font-weight:bold; color:#1f2937;">Geçici Şifre: <span style="background:#f3f4f6; padding:6px 10px; border-radius:6px;">{temp_password}</span></p>
                <p>Bu e-posta yalnızca bilgilendirme amaçlıdır; buton veya link yoktur.</p>
                <p>Eğer bu talebi siz yapmadıysanız, lütfen IT ile iletişime geçin.</p>
                <p>Yataş IT Team</p>
            </body>
        </html>
        """
        
        msg.attach(MIMEText(html_body, 'html'))
        
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        
        return True
    except Exception as e:
        logger.exception(f"E-posta gönderilemedi: {str(e)}")
        st.error(f"E-posta gönderilemedi: {str(e)}")
        return False

def reset_password(reset_token: str, email: str, new_password: str) -> bool:
    """Şifre sıfırlama işlemini tamamla."""
    logger.debug("reset_password called for %s", email)
    user = find_user_by_email(email)
    if not user:
        logger.debug("reset_password: user not found %s", email)
        return False
    
    # Token kontrolü, eski link tabanlı akış için geçerli; artık temp şifre göndermeye geçildi.
    if user.get("password_reset_token") and user.get("password_reset_token") != reset_token:
        return False
    if user.get("password_reset_expires"):
        expires_at = datetime.fromisoformat(user.get("password_reset_expires", "").replace("Z", "+00:00"))
        if datetime.utcnow().replace(tzinfo=None) > expires_at.replace(tzinfo=None):
            return False  # Token süresi dolmuş
    
    # Şifreyi hashle ve kaydet
    users_data = load_users()
    for u in users_data.get("users", []):
        if u.get("email", "").lower() == email.lower():
            u["password_hash"] = hashlib.sha256(new_password.encode()).hexdigest()
            u["password_reset_token"] = None
            u["password_reset_expires"] = None
            break
    
    save_result = save_users(users_data)
    logger.debug("reset_password: save_users returned %s", save_result)
    return save_result

def verify_sso_credentials(email: str, password: str = None) -> dict:
    """SSO doğrulama — users.json'dan kontrol et."""
    import msal
    
    # Kullanıcıyı dosyadan bul
    user = find_user_by_email(email)
    if not user:
        return {"success": False, "message": "Kullanıcı bulunamadı"}
    
    # Kullanıcı aktif mi?
    if not user.get("is_active", False):
        return {"success": False, "message": "Bu kullanıcı hesabı deaktif edilmiştir"}
    
    # Şifre hash'ini kontrol et
    if not password:
        return {"success": False, "message": "Şifre gereklidir"}
    
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    if user.get("password_hash") != password_hash:
        return {"success": False, "message": "Şifre yanlış"}
    
    try:
        # Son login zamanını güncelle
        users_data = load_users()
        for u in users_data.get("users", []):
            if u.get("email", "").lower() == email.lower():
                u["last_login"] = datetime.utcnow().isoformat() + "Z"
                break
        save_users(users_data)
    except Exception as e:
        return {"success": False, "message": f"Login hatası: {str(e)}"}

    # Başarılı login - kullanıcı bilgilerini döndür
    return {
        "success": True,
        "token": f"token_{uuid.uuid4().hex[:16]}",
        "user": {
            "id": user.get("id", ""),
            "email": user.get("email", ""),
            "name": user.get("name", ""),
            "department": user.get("department", ""),
            "position": user.get("position", ""),
            "pernr": user.get("pernr", ""),
            "role": user.get("role", "user"),
            "permissions": user.get("permissions", [])
        }
    }


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

def fetch_top_products_from_azure():
    """
    Azure Table Storage'dan günlük toplanan top 10 ürünleri çeker.
    Demo modda placeholder data döner.
    """
    if DEMO_MODE or not AZURE_STORAGE_CONNECTION_STRING:
        # Demo data
        return [
            {"rank": 1, "product_name": "iPhone 15 Pro", "price": 45999.0, "category": "Elektronik", "image_url": "https://via.placeholder.com/150"},
            {"rank": 2, "product_name": "Samsung Galaxy S24", "price": 38999.0, "category": "Elektronik", "image_url": "https://via.placeholder.com/150"},
            {"rank": 3, "product_name": "Dyson V15", "price": 12999.0, "category": "Ev Elektroniği", "image_url": "https://via.placeholder.com/150"},
            {"rank": 4, "product_name": "Philips Airfryer", "price": 3499.0, "category": "Ev Aletleri", "image_url": "https://via.placeholder.com/150"},
            {"rank": 5, "product_name": "Nike Air Max", "price": 2999.0, "category": "Ayakkabı", "image_url": "https://via.placeholder.com/150"},
            {"rank": 6, "product_name": "Sony WH-1000XM5", "price": 8999.0, "category": "Kulaklık", "image_url": "https://via.placeholder.com/150"},
            {"rank": 7, "product_name": "Arzum Okka", "price": 1499.0, "category": "Kahve Makinesi", "image_url": "https://via.placeholder.com/150"},
            {"rank": 8, "product_name": "Karaca Tencere Seti", "price": 899.0, "category": "Mutfak", "image_url": "https://via.placeholder.com/150"},
            {"rank": 9, "product_name": "Adidas Samba", "price": 2599.0, "category": "Ayakkabı", "image_url": "https://via.placeholder.com/150"},
            {"rank": 10, "product_name": "Xiaomi Robot Süpürge", "price": 4999.0, "category": "Ev Elektroniği", "image_url": "https://via.placeholder.com/150"}
        ]
    
    try:
        # Real Azure Table query
        table_service = TableServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
        table_client = table_service.get_table_client(AZURE_TABLE_NAME)
        
        # Query latest date's data (assume PartitionKey is date in YYYYMMDD format)
        today = datetime.now().strftime("%Y%m%d")
        entities = table_client.query_entities(f"PartitionKey eq '{today}'")
        
        results = []
        for entity in entities:
            results.append({
                "rank": entity.get("Rank", 0),
                "product_name": entity.get("ProductName", ""),
                "price": entity.get("Price", 0.0),
                "category": entity.get("Category", ""),
                "image_url": entity.get("ImageUrl", ""),
                "source": entity.get("Source", ""),
                "url": entity.get("Url", "")
            })
        
        # Sort by rank
        results.sort(key=lambda x: x["rank"])
        return results[:10]
    
    except Exception as e:
        st.error(f"Azure Table'dan veri çekerken hata: {str(e)}")
        return []

def scrape_turkish_ecommerce_sites():
    """Perform a best-effort scrape of several Turkish e-commerce sites and
    return an aggregated list of top products (up to 10). This is a lightweight
    agent implementation using requests + BeautifulSoup. If `AZURE_TABLE` is
    configured the results will also be persisted for later use.
    """
    sites = [
        {"name": "Trendyol", "url": "https://www.trendyol.com/cok-satanlar"},
        {"name": "Hepsiburada", "url": "https://www.hepsiburada.com/cok-satanlar"},
        {"name": "N11", "url": "https://www.n11.com/cok-satanlar"}
    ]

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    collected = []

    # Try Playwright-based scraper first (better for JS-heavy pages)
    try:
        pw_collected = scrape_with_playwright(sites)
        if pw_collected is not None:
            collected.extend(pw_collected)
    except Exception:
        # ignore and fall back to requests-based scraping
        pass

    for site in sites:
        try:
            r = requests.get(site["url"], timeout=10, headers=headers)
            if r.status_code != 200:
                continue

            soup = BeautifulSoup(r.content, "html.parser")

            # Try a few common selectors; most sites use JS so this is best-effort
            cards = []
            for sel in ('.product-card', '.product-item', '.productListContent-item', '.prd', '.p-card'):
                cards = soup.select(sel)
                if cards:
                    break

            if not cards:
                # fallback: find product links
                cards = soup.select('a[href*="/p/"]')[:20]

            for idx, card in enumerate(cards[:20], start=1):
                try:
                    # title
                    title = None
                    for tsel in ('.product-title', '.product-name', 'h3', 'h4', '.prd-name', '.p-card__title'):
                        t = card.select_one(tsel) if hasattr(card, 'select_one') else None
                        if t and t.get_text(strip=True):
                            title = t.get_text(strip=True)
                            break
                    if not title:
                        title = card.get_text(strip=True)[:80]

                    # price
                    price = 0.0
                    for psel in ('.price', '.product-price', '.fiyat', '.p-card__price', '.discountPrice'): 
                        p = card.select_one(psel) if hasattr(card, 'select_one') else None
                        if p and p.get_text(strip=True):
                            price = _parse_price_text(p.get_text(strip=True))
                            break

                    # image
                    img = None
                    if hasattr(card, 'select_one'):
                        im = card.select_one('img')
                        if im:
                            img = im.get('data-src') or im.get('src') or None
                            if img and img.startswith('//'):
                                img = 'https:' + img

                    # url
                    url = ''
                    if hasattr(card, 'get'):
                        a = card if card.name == 'a' else card.select_one('a')
                        if a and a.get('href'):
                            url = a.get('href')
                            if url.startswith('/'):
                                parts = site['url'].split('/')
                                url = parts[0] + '//' + parts[2] + url

                    collected.append({
                        'product_name': title or 'Ürün',
                        'price': price or 0.0,
                        'image_url': img or '',
                        'source': site['name'],
                        'url': url,
                        'rank': idx
                    })
                except Exception:
                    continue

        except Exception:
            continue

    # Aggregate by product name (simple frequency + avg rank) and pick top 10
    if not collected:
        # fallback to demo data
        return fetch_top_products_from_azure()

    agg = {}
    for item in collected:
        key = item['product_name'].strip().lower()
        if not key:
            continue
        if key not in agg:
            agg[key] = {**item, 'count': 0, 'rank_sum': 0}
        agg[key]['count'] += 1
        agg[key]['rank_sum'] += item.get('rank', 0)

    results = []
    for k, v in agg.items():
        avg_rank = v['rank_sum'] / max(1, v['count'])
        results.append({
            'product_name': v['product_name'],
            'price': v['price'],
            'image_url': v['image_url'],
            'source': v['source'],
            'url': v['url'],
            'score': v['count'],
            'avg_rank': avg_rank
        })

    # sort by count desc then avg_rank asc
    results.sort(key=lambda x: (-x['score'], x['avg_rank']))
    top10 = []
    for i, r in enumerate(results[:10], start=1):
        top10.append({
            'rank': i,
            'product_name': r['product_name'],
            'price': r.get('price', 0.0),
            'category': 'Genel',
            'image_url': r.get('image_url', ''),
            'source': r.get('source', ''),
            'url': r.get('url', '')
        })

    # Persist to Azure Table if configured
    if AZURE_STORAGE_CONNECTION_STRING:
        try:
            table_service = TableServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
            table_client = table_service.get_table_client(AZURE_TABLE_NAME)
            today = datetime.now().strftime('%Y%m%d')
            for item in top10:
                entity = {
                    'PartitionKey': today,
                    'RowKey': str(uuid.uuid4()),
                    'Rank': int(item['rank']),
                    'ProductName': item['product_name'],
                    'Price': float(item.get('price', 0.0)),
                    'Category': item.get('category', ''),
                    'ImageUrl': item.get('image_url', ''),
                    'Source': item.get('source', ''),
                    'Url': item.get('url', '')
                }
                try:
                    table_client.create_entity(entity)
                except Exception:
                    # ignore failures to persist
                    pass
        except Exception:
            pass

    return top10
    # Simple approach: just take first 10
    top_products = all_products[:10]
    
    # Save to Azure Table
    try:
        table_service = TableServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
        table_client = table_service.get_table_client(AZURE_TABLE_NAME)
        
        # Create table if not exists
        try:
            table_service.create_table(AZURE_TABLE_NAME)
        except Exception:
            pass  # table already exists
        
        today = datetime.now().strftime("%Y%m%d")
        
        for product in top_products:
            entity = {
                "PartitionKey": today,
                "RowKey": str(uuid.uuid4()),
                "Rank": product["rank"],
                "ProductName": product["product_name"],
                "Price": product["price"],
                "Category": product["category"],
                "ImageUrl": product["image_url"],
                "Source": product["source"],
                "Url": product["url"]
            }
            table_client.upsert_entity(entity)
    
    except Exception as e:
        print(f"Azure Table'a kayıt hatası: {str(e)}")

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
    # URL parametrelerini kontrol et - authorization code callback
    query_params = st.query_params
    auth_code = query_params.get("code")
    reset_token = query_params.get("reset_token")
    reset_email = query_params.get("email")

    # Şifre sıfırlama akışı (devre dışı bırakılabilir)
    if ENABLE_PASSWORD_RESET and reset_token and reset_email:
        with st.container():
            st.subheader("🔐 Şifre Sıfırlama")
            new_pw = st.text_input("Yeni Şifre", type="password", key="reset_new_pw")
            new_pw2 = st.text_input("Yeni Şifre (Tekrar)", type="password", key="reset_new_pw2")
            if st.button("Şifreyi Güncelle", use_container_width=True, key="btn_do_reset"):
                if not new_pw or not new_pw2:
                    st.error("Lütfen şifre alanlarını doldurun")
                elif new_pw != new_pw2:
                    st.error("Şifreler eşleşmiyor")
                else:
                    if reset_password(reset_token, reset_email, new_pw):
                        st.success("Şifre başarıyla güncellendi. Giriş yapabilirsiniz.")
                    else:
                        st.error("Token geçersiz veya süresi dolmuş.")
            st.info("Şifre sıfırlama bağlantısı yalnızca 24 saat geçerlidir.")
            # Removed st.stop() to avoid terminating the Streamlit runtime unexpectedly
            # when users interact with the password reset flow. Allow the script to
            # continue so the server stays up for other sessions.
    
    if auth_code:
        # Microsoft'tan dönen authorization code var - token ile değiştir
        with st.spinner("🔐 Azure AD ile doğrulanıyor..."):
            token_result = exchange_code_for_token(auth_code)
            
            if token_result["success"]:
                # Token başarılı - Graph API'den kullanıcı bilgilerini al
                user_result = get_user_from_graph(token_result["token"])
                
                if user_result["success"]:
                    user_info = user_result["user"]
                    
                    # Session state'e kaydet
                    st.session_state.authenticated = True
                    st.session_state.token = token_result["token"]
                    st.session_state.user_data = user_info
                    st.session_state.page = "menu"
                    
                    # PERNR bul
                    pernr_result = get_pernr_from_email(user_info.get("email", ""))
                    if pernr_result["success"]:
                        st.session_state.user_data["personnel_number"] = pernr_result["pernr"]
                    
                    st.success("✅ Azure AD giriş başarılı!")
                    st.rerun()
                else:
                    st.error(f"❌ Kullanıcı bilgileri alınamadı: {user_result['message']}")
            else:
                st.error(f"❌ Token hatası: {token_result['message']}")
    else:
        # Normal giriş ekranı
        col1, col2, col3 = st.columns([0.5, 2, 0.5])
        with col2:
            
            # Sadece şifre ile giriş
            st.write("**Giriş Yöntemi:** Şifre ile")
            email = st.text_input(
                "E-POSTA",
                placeholder="user@yatas.com",
                label_visibility="visible",
                key="login_email"
            )
            
            password = st.text_input(
                "ŞİFRE",
                type="password",
                placeholder="Şifrenizi girin",
                label_visibility="visible",
                key="login_password"
            )

            if ENABLE_PASSWORD_RESET:
                if st.button("🔑 Şifremi Unuttum", use_container_width=True, key="btn_forgot"):
                    logger.debug("Forgot-password button clicked; email=%s", email)
                    if email:
                        with st.spinner("E-posta gönderiliyor..."):
                            logger.debug("Calling request_password_reset for %s", email)
                            try:
                                ok = request_password_reset(email)
                            except Exception as e:
                                logger.exception("request_password_reset raised: %s", str(e))
                                ok = False
                            logger.debug("request_password_reset returned %s for %s", ok, email)
                            if ok:
                                st.success("Şifre sıfırlama bağlantısı e-posta olarak gönderildi (SMTP yoksa konsola yazılır).")
                            else:
                                st.error("Kullanıcı bulunamadı veya e-posta gönderilemedi.")
                    else:
                        logger.debug("Forgot-password clicked without email")
                        st.error("Lütfen e-posta giriniz")
            else:
                st.info("Şifre sıfırlama şu anda devre dışı bırakılmıştır.")
            
            if st.button("🚀 Şifre ile Giriş Yap", use_container_width=True, key="login_btn"):
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
        
        pass

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
        
        # Proje Analiz butonu (5th button in new row)
        st.write("")  # spacing
        col5, col6, col7, col8 = st.columns(4)
        with col5:
            if st.button("📈 PROJE ANALİZ", use_container_width=True, key="btn_proje_analiz"):
                st.session_state.page = "proje_analiz"
                st.rerun()
        
        # Admin Panel (sadece admin users)
        if st.session_state.user_data.get("role") == "admin":
            st.write("---")
            if st.button("⚙️ ADMIN PANELİ", use_container_width=True, key="btn_admin"):
                st.session_state.page = "admin_panel"
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

    # (employee_photo page removed per request)

    # ADMIN PANEL
    elif st.session_state.page == "admin_panel":
        col1, col2 = st.columns([1, 10])
        with col1:
            if st.button("⬅️", key="back_admin"):
                st.session_state.page = "menu"
                st.rerun()
        with col2:
            st.title("⚙️ Admin Paneli")
        st.write("---")

        # Yeni kullanıcı ekle
        st.subheader("Kullanıcı Ekle")
        with st.form(key="add_user_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                new_email = st.text_input("E-posta")
                new_name = st.text_input("İsim")
                new_department = st.text_input("Departman")
            with c2:
                new_position = st.text_input("Pozisyon")
                new_role = st.selectbox("Rol", options=["user", "admin"], index=0)
                new_pernr = st.text_input("PERNR", placeholder="Opsiyonel")
            submit_add = st.form_submit_button("Ekle")
            if submit_add:
                if new_email and new_name:
                    ok = add_user(new_email, new_name, new_department, new_position, new_role, new_pernr)
                    if ok:
                        st.success("Kullanıcı eklendi ve şifre sıfırlama linki üretildi (SMTP yoksa konsola yazılır).")
                    else:
                        st.error("Kullanıcı zaten var veya kaydedilemedi.")
                else:
                    st.error("E-posta ve isim zorunludur.")

        st.write("---")
        st.subheader("Kullanıcı Listesi")
        users_data = load_users().get("users", [])
        if not users_data:
            st.info("Henüz kullanıcı yok.")
        else:
            for u in users_data:
                c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 1, 2])
                with c1:
                    st.markdown(f"**{u.get('name','')}**")
                    st.caption(u.get('email',''))
                with c2:
                    st.write(u.get('department',''))
                    st.write(u.get('position',''))
                with c3:
                    st.write(f"Rol: {u.get('role','user')}")
                    st.write(f"İzinler: {', '.join(u.get('permissions', []))}")
                with c4:
                    active = u.get('is_active', False)
                    st.write("Aktif" if active else "Pasif")
                with c5:
                    if st.button("Reset Link", key=f"reset_{u.get('email')}"):
                        if request_password_reset(u.get('email','')):
                            st.success(f"Reset linki gönderildi: {u.get('email')}")
                        else:
                            st.error("Gönderilemedi")
                    toggle_label = "Pasifleştir" if u.get('is_active', False) else "Aktifleştir"
                    if st.button(toggle_label, key=f"toggle_{u.get('email')}"):
                        res = update_user_active(u.get('email',''), not u.get('is_active', False))
                        if res:
                            st.rerun()
        st.info("E-posta gönderimi için SMTP bilgilerini .env'de tanımlayın (SMTP_SERVER, SMTP_PORT, SENDER_EMAIL, SENDER_PASSWORD).")

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
    
    # PROJE ANALİZ SAYFASI
    elif st.session_state.page == "proje_analiz":
        if st.button("⬅️ Ana Menü", key="back_from_proje_analiz"):
            st.session_state.page = "menu"
            st.rerun()
        
        st.title("📈 Proje Analiz - Türkiye'de En Çok Satan Ürünler")
        st.write("Günlük olarak toplanan verilerden **top 10** ürünler:")
        
        # Initialize analysis state
        if "analysis_data" not in st.session_state:
            st.session_state.analysis_data = None
        if "last_update" not in st.session_state:
            st.session_state.last_update = None
        
        # Manual refresh button
        if st.button("🔄 Verileri Yenile", key="refresh_analysis"):
            with st.spinner("Gerçek zamanlı veriler toplanıyor..."):
                st.session_state.analysis_data = scrape_turkish_ecommerce_sites()
                st.session_state.last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.rerun()
        
        # Auto-load on first visit: prefer local `trendyol_top10.json` if present
        if st.session_state.analysis_data is None:
            with st.spinner("Canlı veriler yükleniyor (local cache kontrol ediliyor)..."):
                try:
                    # Prefer aggregated multi-site Top-40 if present
                    if os.path.exists('proje_analiz_top40.json'):
                        with open('proje_analiz_top40.json', 'r', encoding='utf-8') as f:
                            raw = json.load(f)
                        raw_items = raw.get('items', raw) if isinstance(raw, dict) else raw
                        st.session_state.analysis_data = _normalize_analysis_items(raw_items)
                        st.session_state.last_update = datetime.fromtimestamp(os.path.getmtime('proje_analiz_top40.json')).strftime('%Y-%m-%d %H:%M:%S')
                    elif os.path.exists('trendyol_top10.json'):
                        with open('trendyol_top10.json', 'r', encoding='utf-8') as f:
                            raw = json.load(f)
                        # If the file contains dict {'products': [...]}, normalize
                        if isinstance(raw, dict) and 'products' in raw:
                            raw_items = raw.get('products', [])
                        elif isinstance(raw, list):
                            raw_items = raw
                        else:
                            raw_items = []
                        # normalize into UI schema
                        st.session_state.analysis_data = _normalize_analysis_items(raw_items)
                        st.session_state.last_update = datetime.fromtimestamp(os.path.getmtime('trendyol_top10.json')).strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        st.session_state.analysis_data = _normalize_analysis_items(scrape_turkish_ecommerce_sites() or [])
                        st.session_state.last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    st.session_state.analysis_data = _normalize_analysis_items(scrape_turkish_ecommerce_sites() or [])
                    st.session_state.last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Display last update time
        if st.session_state.last_update:
            st.caption(f"Son güncelleme: {st.session_state.last_update}")
        
        # Display top 10 products
        data = st.session_state.analysis_data
        if data and len(data) > 0:
            st.subheader("🏆 Top 10 Ürünler")
            
            # Create DataFrame for table display
            df = pd.DataFrame(data)
            st.dataframe(df, use_container_width=True)
            
            # Bar chart for sales rank
            if "rank" in df.columns and "product_name" in df.columns:
                st.subheader("📊 Satış Sıralaması")
                chart_data = df[["product_name", "rank"]].head(10)
                st.bar_chart(chart_data.set_index("product_name"))
            
            # Show images if available
            if "image_url" in df.columns:
                st.write("---")
                st.subheader("Ürün Görselleri")
                per_row = 5
                for i in range(0, min(10, len(df)), per_row):
                    row_data = df.iloc[i:i+per_row]
                    cols = st.columns(len(row_data))
                    for j, (idx, row) in enumerate(row_data.iterrows()):
                        with cols[j]:
                            if pd.notna(row.get("image_url")):
                                try:
                                    st.image(row["image_url"], width=150)
                                except Exception:
                                    st.write("(Görsel yüklenemedi)")
                            st.markdown(f"**{row.get('rank', '-')}. {row.get('product_name', 'Ürün')}**")
                            if pd.notna(row.get("price")):
                                st.write(f"₺{row['price']:.2f}")
        else:
            st.warning("Henüz veri yok. Günlük toplama işlemi çalıştırılıyor...")
            st.info("💡 Agent'lar şu anda Türk e-ticaret sitelerini tarayarak en çok satan ürünleri topluyor.")
    
    # HATA SAYFASI
    elif st.session_state.page == "error":
        st.title("❌ Bir Hata Oluştu")
        st.write("Beklenmeyen bir hata meydana geldi.")
        st.write("Hata detayları:")
        st.json(st.session_state.error_details)
        
        if st.button("🔄 Yeniden Dene", use_container_width=True):
            st.session_state.page = "menu"
            st.rerun()
