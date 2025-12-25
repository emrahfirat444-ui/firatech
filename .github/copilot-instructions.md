# Copilot Instructions - Yataş Streamlit HR Portal

## Project Architecture

**Single-file Streamlit Application (`app.py`)**: A 1300+ line HR/B2C portal combining:
- SSO authentication with demo fallback
- SAP RFC integration via REST API gateway
- Product gallery with web scraping (BeautifulSoup)
- Multi-page navigation (menu, assistant, dashboard, organization, b2c_order)
- Interactive chat interface with AI responses

**Demo Mode First**: The app defaults to `DEMO_MODE=True` (controlled by `SAP_GATEWAY_DEMO` env var). All external connections (SSO, SAP API, web scraping) are disabled in demo mode, returning deterministic demo data. This allows the app to run standalone without dependencies.

## Critical Environment Variables

```bash
# Demo mode control (default: enabled)
SAP_GATEWAY_DEMO=1  # 0/false to enable real external connections

# SSO Config (only used when demo mode disabled)
SSO_URL=""
SSO_CLIENT_ID="yatas_app_2025"
SSO_CLIENT_SECRET=""
SSO_REDIRECT_URI="http://localhost:8501"

# SAP RFC via REST API Gateway (only used when demo mode disabled)
SAP_API_BASE_URL="http://localhost:5000/api"  # or SAP_GATEWAY_URL
SAP_HOST=""
SAP_CLIENT=""
SAP_USER=""
SAP_PASSWORD=""
```

## State Management Patterns

**Session state is the source of truth**. Key state variables:
- `authenticated`, `user_data`, `token` - auth state
- `leave_data` - cached SAP RFC results
- `page` - current view (menu|assistant|dashboard|organization|b2c_order)
- `chat_history` - list of `{"role": "user|assistant|image", "content": ...}`
- `gallery_state` - pagination/preview for product images `{"images": [...], "page": 0, "preview": None, "selected": 0}`
- `b2c_order_items` - shopping cart items

**Always use `st.rerun()` after state mutations** to reflect UI changes immediately.

## Demo User Credentials

Hard-coded in `verify_sso_credentials()`:
- `efirat@yatas.com` / `302619Ge!!` (IT department)
- `demo@yatas.com` / `demo123`
- `admin@yatas.com` / `admin2025`

Passwords are SHA256 hashed. Add new demo users to the `DEMO_USERS` dict.

## SAP Integration Pattern

**Two-tier fallback**:
1. Try REST API (`SAP_API_BASE_URL/leave-balance`, `/pernr-from-email`)
2. If demo mode or API fails → return demo data

See `get_leave_balance_from_sap()` and `get_pernr_from_email()` for reference implementations.

## Web Scraping Strategy

`search_products_detailed()` scrapes Yataş product listings:
- Tries multiple URL patterns: `/ara?q=`, `/arama?q=`, etc.
- Falls back to regex image URL extraction if structured parsing fails
- Returns `[{"image": url, "price": float, "code": str, "title": str}, ...]`
- In demo mode, returns placeholder images from `via.placeholder.com`

**Add new scrapers** following the same pattern: try structured selectors first, fall back to heuristics.

## Page Navigation Flow

```
Login → Menu (4 buttons) → [assistant|dashboard|organization|b2c_order]
                            ↑
                            └── All pages have ⬅️ back button to menu
```

Each page checks `st.session_state.page` and renders accordingly. Use `st.session_state.page = "..."` + `st.rerun()` to navigate.

## Chat Assistant Logic

In `assistant` page, user input triggers:
- **Product keywords** (yatak, yorgan, yastık) → web scrape → populate `gallery_state` → render paginated gallery
- **IT team phrases** → auto-assign user to IT department (updates `user_data['department']`)
- **Default** → call `get_ai_response()` with regex pattern matching for leave/org queries

**Gallery features**: pagination (4 per page), keyboard arrows (JavaScript injection), preview modal, "Sepete Ekle" buttons.

## Docker Deployment (Azure Container Registry)

**Build**: `Dockerfile.app` (Python 3.8, installs requirements, sets `SAP_GATEWAY_DEMO=1`, `PORT=80`)
**Entrypoint**: `docker-entrypoint.sh` runs `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`
**CI/CD**: `.github/workflows/ci-acr-deploy.yml` builds, pushes to ACR, deploys to Azure Web App on `main` branch push

**Required GitHub Secrets**:
- `AZURE_CREDENTIALS` (service principal JSON)
- `ACR_NAME`, `ACR_LOGIN_SERVER`
- `APP_NAME` (Azure Web App name)

## Styling Conventions

**CSS embedded in `st.markdown()` at top of `app.py`**:
- Dark theme inputs (`background: #252631`)
- Gradient buttons (`linear-gradient(90deg,#2b2e3a,#3b3f4d)`)
- Chat bubbles (`.chat-user` right-aligned, `.chat-ai` left with border)
- Gallery thumbnails (`.thumb-wrap`, `.thumb-overlay` on hover)

**Modify styles** in the CSS block (lines ~50-180), use `unsafe_allow_html=True` for custom HTML/CSS.

## Adding New Pages

1. Add button to menu page: `if st.button("🆕 NEW PAGE"): st.session_state.page = "new_page"; st.rerun()`
2. Add elif branch: `elif st.session_state.page == "new_page":`
3. Include back button: `if st.button("⬅️"): st.session_state.page = "menu"; st.rerun()`
4. Implement page logic

## Testing Quick Start

**URL param `?test=1`** auto-logs in as `test@yatas.com`, navigates to assistant, prefills IT department chat message (see lines ~200-220).

**Local run**: `streamlit run app.py` (demo mode enabled by default)
**Production**: Set `SAP_GATEWAY_DEMO=0` and configure real endpoints

## Common Pitfalls

- **Forgetting `st.rerun()`** after state changes → UI won't update
- **Not checking demo mode** in new external integrations → will fail in containerized deployments
- **Modifying gallery state without page bounds check** → index out of range
- **Adding new dependencies** → update `requirements.txt` AND `Dockerfile.app` system deps if needed (e.g., lxml needs libxml2-dev)

## Azure Deploy Script

I added `deploy-to-azure.ps1` to automate these steps:
- Create Resource Group
- Create Azure Container Registry (ACR)
- Build images using `az acr build` (app + gateway) and push to ACR
- Create App Service Plan and two Web Apps (one for the Streamlit app, one optional for gateway)
- Configure Web Apps to pull images from ACR and set app settings
- Create a scoped service principal and write its JSON to `azure-gh-actions-creds.json` (use this as `AZURE_CREDENTIALS` GitHub secret)

Usage (PowerShell):
```powershell
.\deploy-to-azure.ps1 -SubscriptionId <SUB_ID> -ResourceGroup <RG_NAME> -ACRName <ACR_NAME> -AppName <APP_NAME>
```

Notes:
- You must run `az login` interactively or have appropriate Azure CLI auth configured.
- The script sets `SAP_GATEWAY_DEMO=1` on the deployed App by default (safe demo). Change via App Settings in portal to connect to real gateway.
- If you want me to run these steps directly, provide credentialed access details (not recommended publicly). Instead run the script locally and share outputs if you want me to finish remote configuration.

**SAP_API_BASE_URL** değerini aşağıdaki gibi güncelleyin:
```
http://20.105.96.139  (IP adresi ile)
veya
http://firatech-app.northeurope.azurecontainer.io (DNS ile)
```

{
  "clientId": "86bb3e9b-d544-4a06-b7c8-302eb3209226",
  "clientSecret": "vxi8Q~MONEkczNliCNysdXewMUY-Gv~5Cl-45bXL",
  "tenantId": "a9967bb3-3814-4e7f-bee0-428a98fffca7",
  "redirectUri": "http://firatech-app.northeurope.azurecontainer.io/auth/callback"
}

https://portal.azure.com/#view/Microsoft_AAD_IAM/UsersManagementMenuBlade/~/AllUsers
