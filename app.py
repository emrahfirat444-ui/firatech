import streamlit as st
import os
from datetime import datetime
import hashlib
import uuid


# Simple demo-only Streamlit app (demo mode safe)
st.set_page_config(page_title="Yataş Demo", layout="wide")

# Demo mode flag
DEMO_MODE = os.getenv("SAP_GATEWAY_DEMO", "1").lower() in ("1", "true", "yes")


def verify_sso_credentials(email: str, password: str) -> dict:
    """Demo SSO verification using an in-memory user list."""
    DEMO_USERS = {
        "efirat@yatas.com": {"password_hash": hashlib.sha256("302619Ge!!".encode()).hexdigest(), "name": "Emrah Fırat", "pernr": "00012345"},
        "demo@yatas.com": {"password_hash": hashlib.sha256("demo123".encode()).hexdigest(), "name": "Demo Kullanıcı", "pernr": "00099999"},
    }
    email_l = (email or "").lower()
    user = DEMO_USERS.get(email_l)
    if not user:
        return {"success": False, "message": "Kullanıcı bulunamadı (demo)"}
    if hashlib.sha256((password or "").encode()).hexdigest() != user["password_hash"]:
        return {"success": False, "message": "Şifre hatalı"}
    token = f"token_{uuid.uuid4().hex[:16]}"
    return {"success": True, "token": token, "user": {"email": email_l, "name": user["name"], "pernr": user["pernr"]}}


def get_pernr_from_email(email: str) -> dict:
    if DEMO_MODE:
        if not email:
            return {"success": False, "message": "Email verisi eksik"}
        local = email.split("@")[0]
        pernr = f"DEMO{len(local):04d}"
        return {"success": True, "pernr": pernr}
    return {"success": False, "message": "Not implemented in non-demo mode"}


def get_leave_balance_from_sap(pernr: str) -> dict:
    # deterministic demo data based on pernr
    base = (sum(ord(c) for c in (pernr or "")) % 30) + 10
    used = (sum(ord(c) for c in (pernr or "")) % 7)
    remaining = max(0, base - used)
    return {
        "success": True,
        "total_leave_days": base,
        "used_leave_days": used,
        "remaining_leave_days": remaining,
        "pending_leave_requests": 1,
        "personnel_number": pernr,
        "year": datetime.now().year,
        "message": "Demo verisi"
    }


if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user = None


def logout():
    st.session_state.authenticated = False
    st.session_state.user = None
    st.experimental_rerun()


if not st.session_state.authenticated:
    st.title("Yataş - Demo Girişi")
    st.write("Bu demo uygulamasında gerçek SAP bağlantısı yoktur. Demo modunda çalışır.")
    email = st.text_input("E-posta", value="demo@yatas.com")
    password = st.text_input("Şifre", type="password", value="demo123")
    if st.button("Giriş Yap"):
        res = verify_sso_credentials(email, password)
        if res.get("success"):
            st.session_state.authenticated = True
            st.session_state.user = res["user"]
            st.success("Giriş başarılı")
            st.experimental_rerun()
        else:
            st.error(res.get("message", "Giriş başarısız"))
else:
    user = st.session_state.user or {}
    st.sidebar.write(f"**{user.get('name','Kullanıcı')}**")
    st.sidebar.write(user.get('email',''))
    if st.sidebar.button("Çıkış"):
        logout()

    st.title(f"Hoş geldiniz, {user.get('name','Kullanıcı')}")
    st.subheader("İşlemler")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("İzin Bilgisi Görüntüle"):
            pernr = user.get('pernr') or get_pernr_from_email(user.get('email','')).get('pernr')
            leave = get_leave_balance_from_sap(pernr)
            if leave.get('success'):
                st.success("İzin bilgileri (demo)")
                st.metric("Toplam İzin", f"{leave['total_leave_days']} gün")
                st.metric("Kullanılan", f"{leave['used_leave_days']} gün")
                st.metric("Kalan", f"{leave['remaining_leave_days']} gün")
            else:
                st.error("İzin bilgileri alınamadı")
    with col2:
        q = st.text_input("Asistan'a soru sor", placeholder="Kaç günüm kaldı?")
        if st.button("Gönder", key="ask_ai") and q:
            pernr = user.get('pernr') or get_pernr_from_email(user.get('email','')).get('pernr')
            leave = get_leave_balance_from_sap(pernr)
            if any(k in q.lower() for k in ["izin", "kalan", "kaç"]):
                st.info(f"Kalan izin: {leave['remaining_leave_days']} gün")
            else:
                st.write("Demo asistan: İzin, organizasyon ve sipariş ile ilgili sorular sorabilirsiniz.")

    st.write("---")
    st.write("Bu uygulama demo amaçlıdır. Gerçek SAP entegrasyonu için `SAP_GATEWAY_DEMO=0` ve gateway/credentials gereklidir.")
