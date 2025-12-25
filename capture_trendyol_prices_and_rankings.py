from playwright.sync_api import sync_playwright
import json
import re
import time
import os

ROOT = os.path.dirname(__file__)
INPUT = os.path.join(ROOT, 'trendyol_top10.json')
OUTPUT = INPUT

TOP_RANKINGS_KEY = 'top-ranking'

PRICE_RE = re.compile(r"\d[\d\.,]*")
LD_PRICE_RE = re.compile(r'"price"\s*:\s*"?([0-9\.,]+)"?', re.I)


def parse_price_from_jsonld(html):
    # find application/ld+json scripts
    for m in re.finditer(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.I | re.S):
        try:
            j = json.loads(m.group(1))
        except Exception:
            continue
        # offers.price
        if isinstance(j, dict):
            offers = j.get('offers')
            if isinstance(offers, dict):
                p = offers.get('price')
                if p:
                    try:
                        return float(str(p).replace('.', '').replace(',', '.'))
                    except:
                        pass
        # sometimes list
        if isinstance(j, list):
            for item in j:
                if isinstance(item, dict) and 'offers' in item:
                    offers = item.get('offers')
                    if isinstance(offers, dict):
                        p = offers.get('price')
                        if p:
                            try:
                                return float(str(p).replace('.', '').replace(',', '.'))
                            except:
                                pass
    return None


def parse_price_by_regex(text):
    # look for price near TL or ₺
    for m in re.finditer(r'([0-9]{1,3}(?:[\.,][0-9]{3})*(?:[\.,][0-9]{2})?)\s*(?:TL|₺|TRY)', text, re.I):
        raw = m.group(1)
        try:
            return float(raw.replace('.', '').replace(',', '.'))
        except:
            pass
    # fallback generic first match
    m = PRICE_RE.search(text)
    if m:
        raw = m.group(0)
        try:
            return float(raw.replace('.', '').replace(',', '.'))
        except:
            pass
    return None


def enrich_prices_and_rankings():
    # load existing items
    if not os.path.exists(INPUT):
        print('No input file', INPUT)
        return
    with open(INPUT, 'r', encoding='utf-8') as f:
        items = json.load(f)

    # collect product URLs to visit
    product_urls = []
    for it in items:
        url = it.get('url','')
        if url and url.startswith('/'):
            url = 'https://www.trendyol.com' + url
        if url:
            product_urls.append(url)

    top_rankings_responses = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64)')
        page = ctx.new_page()

        # capture top-ranking XHRs
        def on_response(resp):
            try:
                u = resp.url
                if TOP_RANKINGS_KEY in u.lower() or 'top-rankings' in u.lower() or 'top-ranking-contents' in u.lower():
                    try:
                        j = resp.json()
                        top_rankings_responses.append((u,j))
                    except Exception:
                        pass
            except Exception:
                pass
        page.on('response', on_response)

        # visit homepage and some categories to trigger top-rankings
        pages_to_visit = ['https://www.trendyol.com', 'https://www.trendyol.com/magaza/yatas']
        for purl in pages_to_visit:
            try:
                page.goto(purl, wait_until='networkidle', timeout=30000)
            except Exception:
                try:
                    page.goto(purl, timeout=30000)
                except Exception:
                    pass
            time.sleep(1)

        # now visit each product to extract price
        for idx,u in enumerate(product_urls):
            print('Visiting', u)
            try:
                page.goto(u, wait_until='networkidle', timeout=30000)
            except Exception:
                try:
                    page.goto(u, timeout=30000)
                except Exception as e:
                    print('Failed to load', u, e)
                    continue
            time.sleep(1)
            # try JSON-LD
            html = page.content()
            price = parse_price_from_jsonld(html)
            if price is None:
                # try XHR responses captured -> check recent responses
                try:
                    # check last 10 responses
                    # playwright page.evaluate to get performance entries not allowed; we rely on on_response capture above
                    pass
                except Exception:
                    pass
            if price is None:
                price = parse_price_by_regex(html)
            # update items matching this url
            for it in items:
                full = it.get('url','')
                if full and full.startswith('/'):
                    full = 'https://www.trendyol.com' + full
                if full == u:
                    it['price'] = price
            time.sleep(0.5)

        browser.close()

    # if we found top-rankings responses, try to parse product arrays and prepend high-ranked items
    rank_candidates = []
    for (u,j) in top_rankings_responses:
        # walk json and find product objects
        def walk(o):
            if isinstance(o, dict):
                # product detection
                if any(k in o for k in ['productId','id','title']) and any(k in o for k in ['image','images']):
                    # normalize
                    name = o.get('title') or o.get('name') or ''
                    price = None
                    for k in ['price','listPrice','salePrice']:
                        if k in o:
                            try:
                                price = float(o[k])
                            except:
                                pass
                    image = ''
                    for k in ['images','image','imageUrl']:
                        if k in o:
                            v = o[k]
                            if isinstance(v, list) and v:
                                image = v[0]
                            elif isinstance(v, str):
                                image = v
                    url = o.get('url') or o.get('productLink') or ''
                    rank_candidates.append({'product_name':name,'price':price,'image_url':image,'url':url})
                for vv in o.values():
                    walk(vv)
            elif isinstance(o, list):
                for it in o:
                    walk(it)
        try:
            walk(j)
        except Exception:
            pass

    # merge rank_candidates to front if they look better
    merged = []
    seen = set()
    for it in rank_candidates + items:
        key = (it.get('product_name') or '')[:200]
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(it)
        if len(merged) >= 20:
            break

    # write back top 10
    out = merged[:10]
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print('Wrote', OUTPUT, 'items_count=', len(out))

if __name__ == '__main__':
    enrich_prices_and_rankings()
