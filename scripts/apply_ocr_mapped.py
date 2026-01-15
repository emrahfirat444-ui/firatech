from playwright.sync_api import sync_playwright
import json, os, re, time
from pathlib import Path

in_hits = Path('data/trendyol_kadin_ocr_hits.json')
out_raw = Path('data/trendyol_kadin_ocr_top_sellers.json')
out_top20 = Path('trendyol_top20.json')

def _extract_price_from_text(text: str):
    if not text:
        return None
    m = re.search(r'([0-9\.,]+)\s*(TL|₺)', text)
    if m:
        s = m.group(1)
        s = s.replace('.', '').replace(',', '.')
        try:
            return float(s)
        except Exception:
            return None
    m2 = re.search(r'([0-9]{2,}[\.,]?[0-9]*)', text)
    if m2:
        try:
            return float(m2.group(1).replace('.', '').replace(',', '.'))
        except Exception:
            return None
    return None

if not in_hits.exists():
    print('Input hits not found:', in_hits)
    raise SystemExit(1)

with open(in_hits, 'r', encoding='utf-8') as f:
    hits_data = json.load(f)
mapped = hits_data.get('mapped', {})
if not mapped:
    print('No mapped hits found to apply.')
    raise SystemExit(0)

results = []
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    for href, hit in mapped.items():
        try:
            page = browser.new_page()
            page.goto(href, timeout=30000)
            page.wait_for_load_state('networkidle', timeout=10000)
            time.sleep(0.6)
            title = None
            image = None
            price = None
            category_3 = None
            material = None

            # title
            for sel in ['h1', '.pr-new-br', '.product-name', 'h1.pr-header__title', '[data-testid="product-name"]']:
                try:
                    el = page.locator(sel)
                    if el.count()>0:
                        title = el.nth(0).inner_text().strip()
                        if title:
                            break
                except Exception:
                    continue

            # image via JSON-LD or og
            try:
                ld = page.locator('script[type="application/ld+json"]')
                for i in range(min(6, ld.count())):
                    try:
                        txt = ld.nth(i).inner_text()
                        doc = json.loads(txt)
                        if isinstance(doc, dict) and doc.get('image'):
                            iv = doc.get('image')
                            image = iv[0] if isinstance(iv, list) else iv
                            break
                    except Exception:
                        continue
            except Exception:
                pass
            if not image:
                try:
                    meta = page.locator('meta[property="og:image"]')
                    if meta.count()>0:
                        image = meta.nth(0).get_attribute('content')
                except Exception:
                    pass

            # price
            try:
                txt = page.locator('body').inner_text()
                price = _extract_price_from_text(txt)
            except Exception:
                price = None

            # material
            try:
                m = re.search(r'(Malzeme|Materyal|Kuma[şs]|İçerik)[:\s\n]*([A-Za-zÇĞİÖŞÜçğıöşü0-9,\s%-]+)', page.content(), re.I)
                if m:
                    material = m.group(2).strip()
            except Exception:
                material = None

            # category_3 via breadcrumb JSON-LD
            try:
                ld = page.locator('script[type="application/ld+json"]')
                for i in range(min(6, ld.count())):
                    try:
                        txt = ld.nth(i).inner_text()
                        doc = json.loads(txt)
                        if isinstance(doc, dict) and doc.get('@type', '').lower()=='breadcrumblist':
                            items = doc.get('itemListElement', [])
                            if len(items)>=3:
                                category_3 = items[2].get('name')
                                break
                    except Exception:
                        continue
            except Exception:
                pass

            results.append({
                'product_url': href,
                'product_name': title,
                'image_url': image,
                'rank': None,
                'price': price,
                'material': material,
                'category_3': category_3,
                'ocr_hit': hit,
            })
            page.close()
        except Exception as e:
            print('error processing', href, e)
            continue
    browser.close()

# assign ranks by order
for i,r in enumerate(results, start=1):
    r['rank'] = i

os.makedirs('data', exist_ok=True)
with open(out_raw, 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

# write top20 simplified for app
top20 = []
for rec in results[:20]:
    top20.append({
        'rank': rec.get('rank'),
        'product_url': rec.get('product_url'),
        'product_name': rec.get('product_name'),
        'price': rec.get('price'),
        'material': rec.get('material'),
        'image_url': rec.get('image_url'),
        'category_3': rec.get('category_3')
    })
with open(out_top20, 'w', encoding='utf-8') as f:
    json.dump(top20, f, ensure_ascii=False, indent=2)

print('Wrote', out_raw, 'items=', len(results), 'and updated', out_top20)
