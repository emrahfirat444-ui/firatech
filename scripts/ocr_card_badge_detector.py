from playwright.sync_api import sync_playwright
import pytesseract, os, io, time, json
from PIL import Image

# set tesseract cmd if common path exists
for candidate in [r'C:\Program Files\Tesseract-OCR\tesseract.exe', r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe']:
    try:
        if os.path.exists(candidate):
            pytesseract.pytesseract.tesseract_cmd = candidate
            break
    except Exception:
        pass

CATEGORY_URL = 'https://www.trendyol.com/kadin'
OUT = 'data/trendyol_kadin_card_ocr.json'
OUT_TOP20 = 'trendyol_top20.json'
MAX_PRODUCTS = 100
OCR_CONFIG = '--psm 6'
MATCH_TERMS = ['en çok satan','en cok satan','çok satan','cok satan','en çok','en cok']

# crop regions (relative to container box): list of (x_pct, y_pct, w_pct, h_pct)
CROP_REGIONS = [
    (0.0, 0.0, 1.0, 0.4),    # top 40%
    (0.65, 0.0, 0.35, 0.35), # top-right
    (0.0, 0.6, 0.5, 0.4),    # bottom-left
    (0.25, 0.25, 0.5, 0.3),  # center-top
]


def ocr_image_bytes(b):
    img = Image.open(io.BytesIO(b)).convert('RGB')
    # optional: small resize to improve OCR readability
    w,h = img.size
    if w < 400:
        img = img.resize((int(w*2), int(h*2)))
    txt = pytesseract.image_to_string(img, config=OCR_CONFIG)
    return txt


def looks_like_hit(s):
    if not s:
        return False
    ss = s.lower()
    for t in MATCH_TERMS:
        if t in ss:
            return True
    return False


def run():
    os.makedirs('data', exist_ok=True)
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width':1200,'height':900})
        page.goto(CATEGORY_URL, timeout=30000)
        page.wait_for_load_state('networkidle', timeout=10000)
        time.sleep(1)
        # scroll to load
        for _ in range(8):
            page.evaluate('window.scrollBy(0, document.body.scrollHeight/8)')
            time.sleep(0.6)
        # find product containers
        selectors = ['div[class*="product"]','div[class*="p-card"]','[data-testid="product-card"]','article']
        containers = []
        seen = set()
        for sel in selectors:
            try:
                els = page.query_selector_all(sel)
                for e in els:
                    try:
                        box = e.bounding_box()
                    except Exception:
                        box = None
                    href = None
                    try:
                        for a in e.query_selector_all('a'):
                            h = a.get_attribute('href')
                            if not h:
                                continue
                            if ('/p/' in h) or ('/p-' in h) or ('?merchantId' in h):
                                if h.startswith('/'):
                                    h = 'https://www.trendyol.com' + h
                                href = h
                                break
                    except Exception:
                        pass
                    if href and href not in seen and box:
                        seen.add(href)
                        containers.append({'href': href, 'box': box, 'element': e})
                    if len(containers) >= MAX_PRODUCTS:
                        break
            except Exception:
                continue
            if len(containers) >= MAX_PRODUCTS:
                break
        print('Collected containers:', len(containers))
        # for each container, take screenshot clip and crop regions
        for i, c in enumerate(containers, start=1):
            href = c['href']
            box = c['box']
            # expand box slightly
            left = max(0, box['x'] - 4)
            top = max(0, box['y'] - 4)
            width = max(1, box['width'] + 8)
            height = max(1, box['height'] + 8)
            # clip screenshot
            try:
                clip = {'x': left, 'y': top, 'width': width, 'height': height}
                b = page.screenshot(clip=clip)
            except Exception:
                # fallback: element.screenshot
                try:
                    b = c['element'].screenshot()
                except Exception:
                    b = None
            texts = []
            hit = False
            if b:
                for (rx, ry, rw, rh) in CROP_REGIONS:
                    try:
                        img = Image.open(io.BytesIO(b)).convert('RGB')
                        W,H = img.size
                        crop_box = (int(rx*W), int(ry*H), int((rx+rw)*W), int((ry+rh)*H))
                        crop = img.crop(crop_box)
                        bio = io.BytesIO()
                        crop.save(bio, format='PNG')
                        txt = pytesseract.image_to_string(Image.open(io.BytesIO(bio.getvalue())), config=OCR_CONFIG)
                        texts.append(txt.strip())
                        if looks_like_hit(txt):
                            hit = True
                            break
                    except Exception:
                        continue
            results.append({'href': href, 'box': box, 'hit': hit, 'ocr_texts': texts})
            print(f'{i}/{len(containers)} {href} -> hit={hit}')
            time.sleep(0.25)
        browser.close()
    # write results
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    # build top20 from hits
    hits = [r for r in results if r['hit']]
    top = []
    # open each hit to extract title/image/price
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width':1200,'height':900})
        for idx, r in enumerate(hits[:20], start=1):
            try:
                page.goto(r['href'], timeout=30000)
                page.wait_for_load_state('networkidle', timeout=10000)
                time.sleep(0.4)
                title = None
                img = None
                price = None
                try:
                    title_el = page.locator('h1')
                    if title_el.count()>0:
                        title = title_el.nth(0).inner_text().strip()
                except Exception:
                    pass
                try:
                    meta = page.query_selector('meta[property="og:image"]')
                    if meta:
                        img = meta.get_attribute('content')
                except Exception:
                    pass
                try:
                    body = page.locator('body').inner_text()
                    import re
                    m = re.search(r'([0-9\.,]+)\s*(TL|₺)', body)
                    if m:
                        s = m.group(1).replace('.', '').replace(',', '.')
                        price = float(s)
                except Exception:
                    price = None
                top.append({'rank': idx, 'product_url': r['href'], 'product_name': title, 'price': price, 'image_url': img})
            except Exception:
                continue
        browser.close()
    with open(OUT_TOP20, 'w', encoding='utf-8') as f:
        json.dump(top, f, ensure_ascii=False, indent=2)
    print('Wrote', OUT, 'hits=', len(hits), 'and updated', OUT_TOP20)

if __name__ == '__main__':
    run()
