from playwright.sync_api import sync_playwright
import json
import re
import time
import os

KEYWORDS = ["yatak","yorgan","yastik","yatak odasi","telefon","bilgisayar"]
ROOT = os.path.dirname(__file__)
OUTPUT = os.path.join(ROOT, 'trendyol_top10.json')

PRODUCT_KEYS = ('productId','id','product_id')
IMAGE_KEYS = ('image','imageUrl','images','productImage','image_url')
PRICE_KEYS = ('price','listPrice','salePrice','currentPrice','priceValue')
NAME_KEYS = ('title','name','productName','displayName')

collected = {}

def extract_from_obj(obj, source_url=None):
    # obj can be dict or list
    if isinstance(obj, dict):
        # try to detect product-like dict
        # find id
        pid = None
        for k in PRODUCT_KEYS:
            if k in obj:
                pid = obj[k]
                break
        # name
        name = None
        for k in NAME_KEYS:
            if k in obj and isinstance(obj[k], str):
                name = obj[k]
                break
        # price
        price = None
        for k in PRICE_KEYS:
            if k in obj:
                try:
                    price = float(obj[k])
                    break
                except:
                    try:
                        price = float(str(obj[k]).replace('.', '').replace(',', '.'))
                        break
                    except:
                        pass
        # image
        image = None
        for k in IMAGE_KEYS:
            if k in obj:
                v = obj[k]
                if isinstance(v, str) and v.startswith('http'):
                    image = v
                    break
                if isinstance(v, list) and v:
                    if isinstance(v[0], str) and v[0].startswith('http'):
                        image = v[0]
                        break
        # url
        url = None
        if 'url' in obj and isinstance(obj['url'], str):
            url = obj['url']
        if not url and isinstance(source_url, str):
            url = source_url
        if name and (price or image or pid):
            key = str(pid or name)[:180]
            collected[key] = {
                'product_name': name,
                'price': price,
                'image_url': image or '',
                'url': url or '',
            }
        # recurse
        for v in obj.values():
            extract_from_obj(v, source_url)
    elif isinstance(obj, list):
        for it in obj:
            extract_from_obj(it, source_url)


def run_capture():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64)')
        page = ctx.new_page()
        responses = []

        def on_response(resp):
            try:
                url = resp.url
                ct = resp.headers.get('content-type','')
                if 'application/json' in ct or url.endswith('.json') or 'discovery' in url or 'browsing' in url or 'search' in url:
                    # attempt to parse
                    try:
                        j = resp.json()
                        responses.append((url,j))
                    except Exception:
                        pass
            except Exception:
                pass

        page.on('response', on_response)

        for kw in KEYWORDS:
            search_url = f'https://www.trendyol.com/sr?q={kw}'
            print('Navigating', search_url)
            page.goto(search_url, wait_until='networkidle', timeout=30000)
            # wait extra for XHRs
            time.sleep(2)

        # also visit homepage to catch ranking endpoints
        page.goto('https://www.trendyol.com', wait_until='networkidle', timeout=30000)
        time.sleep(2)

        # parse collected responses
        for url,j in responses:
            extract_from_obj(j, source_url=url)

        browser.close()

if __name__ == '__main__':
    run_capture()
    # convert collected dict to list and score by presence of image+price
    items = list(collected.values())
    def score(it):
        s = 0
        if it.get('image_url'):
            s += 3
        if it.get('price'):
            s += 2
        return s
    items.sort(key=score, reverse=True)
    top = items[:20]
    # dedupe by name
    seen = set()
    final = []
    for it in top:
        n = it.get('product_name','').strip()
        if not n or n in seen:
            continue
        seen.add(n)
        final.append(it)
        if len(final) >= 10:
            break
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(final, f, ensure_ascii=False, indent=2)
    print('Wrote', OUTPUT, 'items_count=', len(final))
