from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import json, time, re

sites = [
    {"name":"Trendyol","urls":["https://www.trendyol.com/cok-satanlar","https://www.trendyol.com/sr?st=cok+satanlar"]},
    {"name":"Hepsiburada","urls":["https://www.hepsiburada.com/cok-satanlar","https://www.hepsiburada.com/arama?q=telefon","https://www.hepsiburada.com/arama?q=yeni"]},
    {"name":"N11","urls":["https://www.n11.com/cok-satanlar","https://www.n11.com/arama?q=telefon","https://www.n11.com/arama?q=yeni"]}
]

# heuristics to find JSON with product lists
KEYWORDS = ['product','products','search','listing','popular','best','items','hits','suggest']


def extract_products_from_json(obj):
    """Walk JSON and collect dicts that look like products (have name/title and maybe price/image)."""
    found = []
    def walk(o):
        if isinstance(o, dict):
            keys = set(o.keys())
            if (('name' in keys or 'title' in keys or 'productName' in keys or 'product_name' in keys)
                and any(k.lower().find('price')!=-1 for k in keys)):
                found.append(o)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for it in o:
                walk(it)
    walk(obj)
    return found


def find_price_in_obj(o):
    # recursively search for numeric-looking price fields
    if isinstance(o, dict):
        for k,v in o.items():
            lk = k.lower()
            if 'price' in lk or 'fiyat' in lk or 'amount' in lk or 'discount' in lk:
                try:
                    txt = str(v)
                    # strip non-digit except , and .
                    m = re.search(r"[0-9][0-9.,]{0,}", txt)
                    if m:
                        num = m.group(0).replace(',','')
                        return float(num)
                except Exception:
                    pass
        for v in o.values():
            res = find_price_in_obj(v)
            if res is not None:
                return res
    elif isinstance(o, list):
        for it in o:
            res = find_price_in_obj(it)
            if res is not None:
                return res
    return None


def normalize_product(d):
    name = d.get('productName') or d.get('name') or d.get('title') or d.get('product_name') or d.get('title_tr') or ''
    # price keys
    price = None
    for k in d.keys():
        if 'price' in k.lower():
            try:
                price = float(re.sub(r'[^0-9\.,]','', str(d.get(k))).replace(',',''))
            except Exception:
                try:
                    price = float(str(d.get(k)).split('.')[0])
                except Exception:
                    price = None
    img = d.get('image') or d.get('imageUrl') or d.get('image_url') or d.get('thumbnail') or ''
    url = d.get('url') or d.get('productUrl') or d.get('detailUrl') or ''
    return {'name': name, 'price': price, 'image': img, 'url': url}


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    results = {}
    for site in sites:
        print('---', site['name'], '---')
        page = browser.new_page()
        collected_jsons = []
        product_hits = []

        def on_response(resp):
            try:
                url = resp.url
                low = url.lower()
                if any(k in low for k in KEYWORDS) or 'api' in low or 'search' in low:
                    ct = resp.headers.get('content-type','')
                    if 'application/json' in ct:
                        try:
                            j = resp.json()
                            collected_jsons.append({'url':url,'json':j})
                        except Exception:
                            pass
            except Exception:
                pass

        page.on('response', on_response)
        try:
            # visit multiple candidate URLs per site to trigger different XHRs
            for url in site.get('urls', [site.get('url')]):
                try:
                    page.goto(url, timeout=30000)
                except Exception:
                    pass
            # try cookie accept
            for sel in ["button:has-text('Kabul')","button:has-text('KABUL')","button:has-text('Kabul Et')","button:has-text('Accept')", "button:has-text('Tümünü kabul et')"]:
                try:
                    el = page.query_selector(sel)
                    if el:
                        el.click(timeout=2000)
                        time.sleep(0.5)
                except Exception:
                    pass
            # scroll to load
            for _ in range(8):
                page.evaluate('window.scrollBy(0, document.body.scrollHeight)')
                time.sleep(0.8)
            page.wait_for_load_state('networkidle', timeout=10000)

            # analyze collected JSONs
            print('collected json responses:', len(collected_jsons))
            found = []
            for idx,jr in enumerate(collected_jsons):
                try:
                    j = jr['json']
                    prods = extract_products_from_json(j)
                    if prods:
                        for pitem in prods:
                            # try to extract price
                            price = find_price_in_obj(pitem)
                            norm = normalize_product(pitem)
                            if norm['price'] is None and price is not None:
                                norm['price'] = price
                            if norm['name']:
                                found.append(norm)
                except Exception:
                    continue
            # dedupe by name
            seen = {}
            out = []
            for it in found:
                n = it['name'].strip()
                if not n: continue
                if n in seen: continue
                seen[n]=True
                out.append(it)
            print('extracted products:', len(out))
            # sort so that items with price come first (desc by price)
            with_price = [i for i in out if i.get('price') is not None]
            without = [i for i in out if i.get('price') is None]
            with_price.sort(key=lambda x: x.get('price') or 0, reverse=True)
            final = with_price + without
            # save top 10 for Trendyol to file
            if site['name'].lower().find('trendyol')!=-1 and final:
                try:
                    import pathlib
                    p = pathlib.Path('trendyol_top10.json')
                    p.write_text(json.dumps(final[:10], ensure_ascii=False, indent=2))
                    print('wrote trendyol_top10.json')
                except Exception as e:
                    print('could not write trendyol file', e)
            if final:
                print(json.dumps(final[:10], ensure_ascii=False, indent=2))
            else:
                print('no products extracted from JSONs')

            # also attempt DOM heuristic
            html = page.content()
            soup = BeautifulSoup(html,'html.parser')
            sels = ['.p-card','.p-card__content','.product-card','.product-item','.productListContent-item','.prd','.product','li.search-item','.catalog-list .product','.product-grid .product-item','.column .product']
            cards = []
            for s in sels:
                cards = soup.select(s)
                if cards:
                    break
            print('dom cards found:', len(cards))
            dom_out = []
            for c in cards[:30]:
                t = c.get_text(strip=True)
                if t and len(t)>3:
                    dom_out.append(t[:80])
            if dom_out:
                print('dom sample:', dom_out[:10])

            results[site['name']] = {'json_responses': len(collected_jsons), 'products_extracted': len(out), 'dom_cards': len(cards)}
        except Exception as e:
            print('error for', site['name'], str(e))
        finally:
            try:
                page.close()
            except Exception:
                pass

    try:
        browser.close()
    except Exception:
        pass

print('SUMMARY')
print(json.dumps(results, ensure_ascii=False, indent=2))
