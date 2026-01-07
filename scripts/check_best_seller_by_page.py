from playwright.sync_api import sync_playwright
import time, json, os, re, argparse
from pathlib import Path

match_texts = ['En Çok Satan', 'En Çok', 'Çok Satan', 'Çok satan']


def looks_like_best(text: str):
    if not text:
        return False
    s = text.lower()
    for t in match_texts:
        if t.lower() in s:
            return True
    return False


def collect_category_links(page, max_products=200):
    # try to find product anchors inside likely containers first, fallback to any /p/ anchors
    hrefs = []
    seen = set()
    cont_selectors = ['div[class*="product"]', 'div[class*="p-card"]', '[data-testid="product-card"]', 'article']
    for sel in cont_selectors:
        try:
            els = page.query_selector_all(sel)
            for e in els:
                try:
                    for a in e.query_selector_all('a'):
                        h = a.get_attribute('href')
                        if not h:
                            continue
                        if ('/p/' in h) or ('/p-' in h) or ('?merchantId' in h):
                            if h.startswith('/'):
                                h = 'https://www.trendyol.com' + h
                            if h in seen:
                                continue
                            seen.add(h)
                            hrefs.append(h)
                            if len(hrefs) >= max_products:
                                return hrefs
                except Exception:
                    continue
        except Exception:
            continue
    # fallback
    try:
        anchors = page.query_selector_all('a[href]')
        for a in anchors:
            try:
                h = a.get_attribute('href')
                if not h:
                    continue
                if ('/p/' in h) or ('/p-' in h) or ('?merchantId' in h):
                    if h.startswith('/'):
                        h = 'https://www.trendyol.com' + h
                    if h in seen:
                        continue
                    seen.add(h)
                    hrefs.append(h)
                    if len(hrefs) >= max_products:
                        break
            except Exception:
                continue
    except Exception:
        pass
    return hrefs


def check_product_page(page, url):
    try:
        page.goto(url, timeout=30000)
        page.wait_for_load_state('networkidle', timeout=10000)
        time.sleep(0.4)
    except Exception:
        return False, {}
    # quick direct locator check
    try:
        if page.locator('text="En Çok Satan"').count() > 0:
            return True, {'reason': 'text-locator'}
    except Exception:
        pass
    # try variants
    try:
        for t in match_texts:
            if page.locator(f'text="{t}"').count() > 0:
                return True, {'reason': f'locator-{t}'}
    except Exception:
        pass
    # scan some likely badge selectors
    badge_selectors = ['[class*="badge"]', '[class*="rozet"]', '[class*="ribbon"]', '.badge', '.rozet', '.ribbon', '[data-badge]']
    try:
        for sel in badge_selectors:
            els = page.query_selector_all(sel)
            for e in els:
                try:
                    txt = e.inner_text()
                    if looks_like_best(txt):
                        return True, {'reason': f'badge-{sel}', 'badge_text': txt}
                except Exception:
                    continue
    except Exception:
        pass
    # search page text
    try:
        body = page.locator('body').inner_text()
        if looks_like_best(body):
            return True, {'reason': 'body-text'}
    except Exception:
        pass
    # search JSON-LD for indicators
    try:
        sds = page.query_selector_all('script[type="application/ld+json"]')
        for i in range(min(6, sds.count())):
            try:
                txt = sds.nth(i).inner_text()
                j = json.loads(txt)
                if isinstance(j, dict):
                    # look for any value containing the match texts
                    sj = json.dumps(j, ensure_ascii=False).lower()
                    for t in match_texts:
                        if t.lower() in sj:
                            return True, {'reason': 'json-ld', 'snippet': t}
            except Exception:
                continue
    except Exception:
        pass
    return False, {}


def run():
    parser = argparse.ArgumentParser(description='Check product pages for best-seller badges and extract product data')
    parser.add_argument('--category-url', default='https://www.trendyol.com/kadin', help='Category URL to scrape')
    parser.add_argument('--max-products', type=int, default=200, help='Maximum products to check')
    parser.add_argument('--out-raw', default='data/trendyol_kadin_page_checked.json', help='Output JSON file for all hits')
    parser.add_argument('--out-top20', default='trendyol_top20.json', help='Output JSON file for top 20 hits')
    args = parser.parse_args()
    
    out = []
    os.makedirs('data', exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width':1200,'height':900})
        page.goto(args.category_url, timeout=30000)
        page.wait_for_load_state('networkidle', timeout=10000)
        time.sleep(1)
        links = collect_category_links(page, max_products=args.max_products)
        print('Collected links:', len(links))
        for i,link in enumerate(links, start=1):
            ok, info = check_product_page(page, link)
            print(i, link, '=>', ok, info)
            if ok:
                # extract minimal product info
                try:
                    title = page.locator('h1').nth(0).inner_text().strip()
                except Exception:
                    title = None
                try:
                    img = None
                    meta = page.query_selector('meta[property="og:image"]')
                    if meta:
                        img = meta.get_attribute('content')
                except Exception:
                    img = None
                try:
                    body = page.locator('body').inner_text()
                    price = None
                    m = re.search(r'([0-9\.,]+)\s*(TL|₺)', body)
                    if m:
                        s = m.group(1).replace('.', '').replace(',', '.')
                        price = float(s)
                except Exception:
                    price = None
                out.append({'product_url': link, 'product_name': title, 'image_url': img, 'reason': info, 'price': price})
            # polite delay
            time.sleep(0.35)
            if len(out) >= args.max_products:
                break
        browser.close()
    with open(args.out_raw, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    # write top20
    top20 = out[:20]
    with open(args.out_top20, 'w', encoding='utf-8') as f:
        json.dump(top20, f, ensure_ascii=False, indent=2)
    print('Wrote', args.out_raw, 'items=', len(out), 'and updated', args.out_top20)

if __name__ == '__main__':
    run()
