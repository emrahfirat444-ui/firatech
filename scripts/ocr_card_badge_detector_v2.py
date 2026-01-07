from playwright.sync_api import sync_playwright
import pytesseract, os, io, time, json
from PIL import Image

# configure tesseract
for candidate in [r'C:\Program Files\Tesseract-OCR\tesseract.exe', r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe']:
    try:
        if os.path.exists(candidate):
            pytesseract.pytesseract.tesseract_cmd = candidate
            break
    except Exception:
        pass

CATEGORY_URL = 'https://www.trendyol.com/kadin'
OUT = 'data/trendyol_kadin_card_ocr_v2.json'
OUT_TOP20 = 'trendyol_top20.json'
MAX_PRODUCTS = 50
OCR_PSMS = [6, 11, 3]
OCR_LANGS = ['tur', 'eng', 'tur+eng']
MATCH_TERMS = ['en çok satan','en cok satan','çok satan','cok satan','en çok','en cok']

# crop regions relative to screenshot (x0,y0 is top-left): list of (left_pct, top_pct, right_pct, bottom_pct)
CROP_REGIONS = [
    (0.0, 0.0, 1.0, 0.35),   # top 35%
    (0.6, 0.0, 1.0, 0.35),   # top-right
    (0.0, 0.0, 0.4, 0.4),    # top-left
    (0.25, 0.1, 0.75, 0.5),  # center-top
    (0.0, 0.0, 1.0, 1.0),    # full clip fallback
]


def ocr_from_bytes(b):
    img = Image.open(io.BytesIO(b)).convert('RGB')
    w,h = img.size
    if w < 400:
        img = img.resize((int(w*2), int(h*2)))
    # try multiple psm/lang combos
    for lang in OCR_LANGS:
        for p in OCR_PSMS:
            try:
                cfg = f'--psm {p}'
                txt = pytesseract.image_to_string(img, lang=lang, config=cfg)
                if txt and txt.strip():
                    return txt
            except Exception:
                continue
    return ''


def looks_like_hit(s):
    if not s:
        return False
    ss = s.lower()
    for t in MATCH_TERMS:
        if t in ss:
            return True
    return False


def expand_box(box, pad=8, minw=50, minh=50):
    x = max(0, box['x'] - pad)
    y = max(0, box['y'] - pad)
    w = max(minw, box['width'] + pad*2)
    h = max(minh, box['height'] + pad*2)
    return {'x': x, 'y': y, 'width': w, 'height': h}


def run():
    os.makedirs('data', exist_ok=True)
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width':1400,'height':1200})
        page.goto(CATEGORY_URL, timeout=30000)
        page.wait_for_load_state('networkidle', timeout=10000)
        time.sleep(1)
        # scroll to load more
        for _ in range(30):
            page.evaluate('window.scrollBy(0, document.body.scrollHeight/20)')
            time.sleep(0.6)
        # collect anchors with product links (match /p/, -p- and merchantId variants)
        anchors = page.query_selector_all('a[href*="-p-"], a[href*="/p/"], a[href*="?merchantId"]')
        hrefs = []
        seen = set()
        for a in anchors:
            try:
                h = a.get_attribute('href')
            except Exception:
                h = None
            if not h:
                continue
            if ('/p/' in h) or ('/p-' in h) or ('?merchantId' in h):
                if h.startswith('/'):
                    h = 'https://www.trendyol.com' + h
                if h in seen:
                    continue
                seen.add(h)
                hrefs.append({'href': h, 'anchor': a})
            if len(hrefs) >= MAX_PRODUCTS:
                break
        print('Collected hrefs:', len(hrefs))
        # for each href, determine clip area (anchor bbox or nearest ancestor with bbox)
        for i, item in enumerate(hrefs, start=1):
            href = item['href']
            anchor = item['anchor']
            box = None
            try:
                box = anchor.bounding_box()
            except Exception:
                box = None
            # if anchor has no box, try parent chain
            if not box:
                try:
                    el = anchor
                    for _ in range(6):
                        el = el.evaluate_handle('e => e.parentElement')
                        if not el:
                            break
                        try:
                            b = el.bounding_box()
                            if b:
                                box = b
                                break
                        except Exception:
                            continue
                except Exception:
                    box = None
            if not box:
                # skip if no geometry
                print(f'{i}/{len(hrefs)} {href} -> no box, skip')
                results.append({'href': href, 'hit': False, 'reason': 'no-box'})
                continue
            clip = expand_box(box, pad=6)
            # screenshot clip
            try:
                bts = page.screenshot(clip=clip)
            except Exception:
                try:
                    bts = anchor.screenshot()
                except Exception:
                    bts = None
            ocr_texts = []
            hit = False
            if bts:
                try:
                    img = Image.open(io.BytesIO(bts)).convert('RGB')
                    W,H = img.size
                    for (l,t,r,b) in CROP_REGIONS:
                        try:
                            crop_box = (int(l*W), int(t*H), int(r*W), int(b*H))
                            crop = img.crop(crop_box)
                            buf = io.BytesIO()
                            crop.save(buf, format='PNG')
                            txt = ocr_from_bytes(buf.getvalue())
                            txts = txt.strip() if txt else ''
                            ocr_texts.append(txts)
                            if looks_like_hit(txts):
                                hit = True
                                break
                        except Exception:
                            continue
                except Exception:
                    pass
            results.append({'href': href, 'hit': hit, 'ocr_texts': ocr_texts})
            print(f'{i}/{len(hrefs)} {href} -> hit={hit}')
            time.sleep(0.25)
        browser.close()
    # write results
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    # build top20
    hits = [r for r in results if r['hit']]
    top = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width':1400,'height':1200})
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
