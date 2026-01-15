from playwright.sync_api import sync_playwright
from PIL import Image
import pytesseract
import io, os, json, time

# Note: pytesseract requires the Tesseract binary on PATH. This script will detect if tesseract is available.

# Try common install locations and set pytesseract cmd if found (helps when PATH not refreshed)
for candidate in [r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe', r'C:\\Program Files (x86)\\Tesseract-OCR\\tesseract.exe']:
    try:
        if os.path.exists(candidate):
            pytesseract.pytesseract.tesseract_cmd = candidate
            break
    except Exception:
        pass
CATEGORY_URL = 'https://www.trendyol.com/kadin'
OUT_JSON = os.path.join('data', 'trendyol_kadin_ocr_hits.json')

# OCR settings
OCR_CONFIG = '--psm 6'
SEARCH_TEXT = 'En Çok Satan'

# viewport scroll step
STEP_PX = 800
MAX_STEPS = 40


def tesseract_available():
    try:
        v = pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def find_badge_positions(page):
    """Scroll the page, capture viewport screenshots, run OCR and return list of bounding boxes in page coordinates where SEARCH_TEXT was found."""
    hits = []
    viewport_height = page.evaluate('() => window.innerHeight')
    total_height = page.evaluate('() => document.body.scrollHeight')
    max_steps = int(min(MAX_STEPS, (total_height // STEP_PX) + 2))
    y = 0
    for step in range(max_steps):
        page.evaluate(f'() => window.scrollTo(0, {y})')
        time.sleep(0.6)
        screenshot = page.screenshot(full_page=False)
        img = Image.open(io.BytesIO(screenshot)).convert('RGB')
        # run OCR
        ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT, config=OCR_CONFIG)
        n_boxes = len(ocr_data['level'])
        for i in range(n_boxes):
            txt = ocr_data['text'][i]
            if not txt:
                continue
            if SEARCH_TEXT.lower() in txt.lower() or SEARCH_TEXT.split()[0].lower() in txt.lower():
                # get bounding box in viewport coords
                x, y0, w, h = (ocr_data['left'][i], ocr_data['top'][i], ocr_data['width'][i], ocr_data['height'][i])
                # convert viewport y to page y by adding scroll y
                scroll_y = page.evaluate('() => window.scrollY')
                page_x = x
                page_y = scroll_y + y0
                hits.append({'page_x': page_x, 'page_y': page_y, 'w': w, 'h': h, 'text': txt})
        y += STEP_PX
        if y > total_height:
            break
    return hits


def map_hits_to_product_links(page, hits):
    """Given page and hits in page coordinates, find the nearest product link (anchor) whose bounding box covers the hit point.
    Returns dict of href->hit info.
    """
    mapped = {}
    anchors = page.query_selector_all('a')
    # collect anchor bounding boxes
    anchors_meta = []
    for a in anchors:
        try:
            href = a.get_attribute('href')
            if not href:
                continue
            box = a.bounding_box()
            if not box:
                continue
            anchors_meta.append({'href': href, 'box': box})
        except Exception:
            continue
    for h in hits:
        hx = h['page_x'] + h.get('w', 0)/2
        hy = h['page_y'] + h.get('h', 0)/2
        # find anchors whose box contains this center
        found = None
        for am in anchors_meta:
            b = am['box']
            left, top = b['x'], b['y']
            right, bottom = left + b['width'], top + b['height']
            if left <= hx <= right and top <= hy <= bottom:
                found = am['href']
                break
        if found:
            # normalize href
            if found.startswith('/'):
                found = 'https://www.trendyol.com' + found
            mapped[found] = h
    return mapped


def run():
    if not tesseract_available():
        print('Tesseract binary not found on system. OCR will fail. Please install Tesseract (https://github.com/tesseract-ocr/tesseract)')
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width':1200,'height':900})
        page.goto(CATEGORY_URL, timeout=30000)
        page.wait_for_load_state('networkidle', timeout=10000)
        time.sleep(1)
        hits = find_badge_positions(page)
        mapped = map_hits_to_product_links(page, hits)
        # also collect first 200 anchors for fallback
        anchors = []
        for a in page.query_selector_all('a')[:400]:
            try:
                href = a.get_attribute('href')
                if href and '/p/' in href:
                    if href.startswith('/'):
                        href = 'https://www.trendyol.com' + href
                    if href not in anchors:
                        anchors.append(href)
            except Exception:
                continue
        out = {'hits': hits, 'mapped': mapped, 'anchors_first200': anchors[:200]}
        os.makedirs('data', exist_ok=True)
        with open(OUT_JSON, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print('Wrote', OUT_JSON, 'hits=', len(hits), 'mapped=', len(mapped), 'anchors_first200=', len(anchors[:200]))
        browser.close()

if __name__ == '__main__':
    run()
