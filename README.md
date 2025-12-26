# Firatech - Streamlit Deploy Hazırlığı

Kısa notlar ve adımlar — Streamlit Community Cloud üzerinde uygulamayı hızlıca çalıştırmak için:

1. GitHub hesabınızda bu repoya erişin (repo: `emrahfirat444-ui/firatech`).
2. Gerekli dosyalar repoda mevcut:
   - `app.py` — ana Streamlit uygulaması
   - `requirements.txt` — Python bağımlılıkları
   - `.streamlit/config.toml` — Cloud için temel ayarlar
3. Hassas veriler:
   - Orijinal kullanıcı verileri `users.example.json` içinde saklanıyor.
   - Prod için `users.json` dosyası demo kullanıcıyla bırakıldı. Gerçek kullanıcı verilerini repoya koymayın.
4. Deploy adımları (Streamlit Cloud):
   - https://share.streamlit.io adresine gidin ve GitHub ile giriş yapın.
   - `New app` → Repo: `emrahfirat444-ui/firatech`, Branch: `main`, File: `app.py` seçin → `Deploy`.
   - Gerekli environment/secrets (SSO, SMTP, vb.) varsa uygulama ayarlarından `Secrets` bölümüne ekleyin.
5. Eğer benim yerime deploy etmemi isterseniz: Streamlit hesabınıza erişim veya paylaşım izni vermeniz gerekir; bunun yerine ben repoyu hazır hale getirdim.

Smoke test: deploy bittikten sonra gelen URL'yi açıp giriş formunu test edin (demo kullanıcı: `demo@example.com` / şifre: `123456`).
